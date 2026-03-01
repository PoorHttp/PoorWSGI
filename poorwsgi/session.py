"""PoorSession self-contained cookie class.

:Classes:   NoCompress, PoorSession
:Functions: hidden, get_token, check_token
"""
from hashlib import sha512, sha256
from json import dumps, loads
from base64 import b64decode, b64encode
from logging import getLogger
from time import time
from typing import Union, Dict, Any, Optional

import bz2

from http.cookies import SimpleCookie

from poorwsgi.headers import Headers
from poorwsgi.request import Request
from poorwsgi.response import Response

log = getLogger("poorwsgi")  # pylint: disable=invalid-name

# pylint: disable=unsubscriptable-object
# pylint: disable=consider-using-f-string


def hidden(text: Union[str, bytes], passwd: Union[str, bytes]) -> bytes:
    """(En|de)crypts text with a SHA hash of the password via XOR.

    text
        Raw data to (en|de)crypt.
    passwd
        The password.
    """
    if isinstance(passwd, bytes):
        passwd = sha512(passwd).digest()
    else:
        passwd = sha512(passwd.encode("utf-8")).digest()
    passlen = len(passwd)

    # text must be bytes
    if isinstance(text, str):
        text = text.encode("utf-8")

    if isinstance(text, str):       # if text is str
        retval = ''
        for i, val in enumerate(text):
            retval += chr(ord(val) ^ ord(passwd[i % passlen]))
    else:                           # if text is bytes
        retval = bytearray()
        for i, val in enumerate(text):
            retval.append(val ^ passwd[i % passlen])

    return retval


def get_token(secret: str, client: str, timeout: Optional[int] = None,
              expired: int = 0):
    """Creates a token from a secret and client string.

    If timeout is set, the token contains a time aligned with twice this value.
    This is because the creation time can be very close to the computed time.
    """
    if timeout is None:
        text = "%s%s" % (secret, client)
    else:
        if expired == 0:
            now = int(time() / timeout) * timeout   # shift to start time
            expired = now + 2 * timeout
        text = "%s%s%s" % (secret, expired, client)

    return sha256(text.encode()).hexdigest()


def check_token(token: str, secret: str, client: str,
                timeout: Optional[int] = None):
    """Checks if the token is correct.

    The secret, client, and timeout arguments must match those used when
    the token was generated. If timeout is set, the token must not be
    older than 2 * timeout.
    """
    if timeout is None:
        return token == get_token(secret, client)

    now = int(time() / timeout) * timeout
    expired = now + timeout
    new_token = get_token(secret, client, timeout, expired)
    if token == new_token:
        return True

    expired += timeout
    new_token = get_token(secret, client, timeout, expired)
    return token == new_token


class SessionError(RuntimeError):
    """Base Exception for Session."""


class NoCompress:
    """Fake compress class/module with two static methods for PoorSession.

    If the compress parameter is None, this class is used.
    """
    @staticmethod
    def compress(data, compresslevel=0):  # pylint: disable=unused-argument
        """Accepts data and compresslevel, and returns data unchanged."""
        return data

    @staticmethod
    def decompress(data):
        """Accepts data and returns it unchanged."""
        return data


class PoorSession:
    """A self-contained cookie with session data.

    You can store or read data from the object via the PoorSession.data
    variable, which must be a dictionary. Data is stored to the cookie by
    JSON serialization and then hidden with app.secret_key. Therefore, it
    must be set on the Application object or with the poor_SecretKey
    environment variable. Be careful with stored objects. You can add
    objects with a little Python trick:

    .. code:: python

        sess = PoorSession(app.secret_key)

        sess.data['class'] = obj.__class__.__name__   # write to cookie
        sess.data['dict'] = obj.__dict__.copy()

        obj = globals()[sess.data['class']]()         # read from cookie
        obj.__dict__ = sess.data['dict'].copy()

    For a better solution, you can create export and import methods for
    your object like this:

    .. code:: python

        class Obj:
            def from_dict(self, d):
                self.attr1 = d['attr1']
                self.attr2 = d['attr2']

            def to_dict(self):
                return {'attr1': self.attr1, 'attr2': self.attr2}

        obj = Obj()
        sess = PoorSession(app.secret_key)

        sess.data['name'] = obj.__class__.__name__    # write to cookie
        sess.data['dict'] = obj.to_dict()

        obj = globals()[sess.data['name']]()          # read from cookie
        obj.from_dict(sess.data['dict'])
    """

    def __init__(self, secret_key: Union[Request, str, bytes],
                 expires: int = 0, max_age: Optional[int] = None,
                 domain: str = '', path: str = '/', secure: bool = False,
                 same_site: bool = False, compress=bz2, sid: str = 'SESSID'):
        """Constructor.

        Arguments:
            expires
                Cookie ``Expires`` time in seconds. If it is 0, no expiration
                is set.
            max_age
                Cookie ``Max-Age`` attribute. If both expires and max-age are
                set, max_age has precedence.
            domain
                The cookie ``Host`` to which the cookie will be sent.
            path
                The cookie ``Path`` that must exist in the requested URL.
            secure
                If the ``Secure`` cookie attribute will be sent.
            same_site
                The ``SameSite`` attribute. When set, it can be one of
                ``Strict|Lax|None``. By default, the attribute is not
                set, which browsers default to ``Lax``.
            compress
                Can be ``bz2``, ``gzip.zlib``, or any other, which has
                standard compress and decompress methods. Or it can be
                ``None`` to not use any compressing method.
            sid
                The cookie key name.

        .. code:: python

            session_config = {
                'expires': 3600,  # one hour
                'max_age': 3600,
                'domain': 'example.net',
                'path': '/application',
                'secure': True,
                'same_site': True,
                'compress': gzip,
                'sid': 'MYSID'
            }

            session = PoorSession(app.secret_key, **session_config)
            try:
                session.load(req.cookies)
            except SessionError as err:
                log.error("Invalid session: %s", str(err))

        *Changed in version 2.4.x*: Use app.secret_key in the
        constructor, and then call the load method.
        """
        if not isinstance(secret_key, (str, bytes)):  # backwards compatibility
            log.warning('Do not use request in PoorSession constructor, '
                        'see new api and call load method manually.')
            if secret_key.secret_key is None:
                raise SessionError("poor_SecretKey is not set!")
            self.__secret_key = secret_key.secret_key
        else:
            self.__secret_key = secret_key

        self.__sid = sid
        self.__expires = expires
        self.__max_age = max_age
        self.__domain = domain
        self.__path = path
        self.__secure = secure
        self.__same_site = same_site
        self.__cps = compress if compress is not None else NoCompress

        # data is session dictionary to store user data in cookie
        self.data: Dict[Any, Any] = {}
        self.cookie: SimpleCookie = SimpleCookie()
        self.cookie[sid] = ''

        if not isinstance(secret_key, (str, bytes)):  # backwards compatibility
            self.load(secret_key.cookies)

    def load(self, cookies: Optional[SimpleCookie]):
        """Loads the session from the request's cookie."""
        if not isinstance(cookies, SimpleCookie) or self.__sid not in cookies:
            return
        raw = cookies[self.__sid].value

        if raw:
            try:
                self.data = loads(hidden(self.__cps.decompress
                                         (b64decode(raw.encode())),
                                         self.__secret_key))
            except Exception as err:
                log.info(repr(err))
                raise SessionError("Bad session data.") from err

            if not isinstance(self.data, dict):
                raise SessionError("Cookie data is not dictionary!")

    def write(self):
        """Stores data to the cookie value.

        This method is called automatically in the header method.
        """
        raw = b64encode(self.__cps.compress(hidden(dumps(self.data),
                                                   self.__secret_key), 9))
        raw = raw if isinstance(raw, str) else raw.decode()
        self.cookie[self.__sid] = raw
        self.cookie[self.__sid]['HttpOnly'] = True

        if self.__domain:
            self.cookie[self.__sid]['Domain'] = self.__domain
        if self.__path:
            self.cookie[self.__sid]['path'] = self.__path
        if self.__secure:
            self.cookie[self.__sid]['Secure'] = True
        if self.__same_site:
            self.cookie[self.__sid]['SameSite'] = self.__same_site
        if self.__expires:
            self.cookie[self.__sid]['expires'] = self.__expires
        if self.__max_age is not None:
            self.cookie[self.__sid]['Max-Age'] = self.__max_age

        return raw

    def destroy(self):
        """Destroys the session by setting the cookie's expires value
        to the past (-1).

        Ensures that data cannot be changed:
        https://stackoverflow.com/a/5285982/8379994
        """
        self.cookie[self.__sid]['expires'] = -1
        if self.__max_age is not None:
            self.cookie[self.__sid]['Max-Age'] = -1
        self.cookie[self.__sid]['HttpOnly'] = True
        if self.__secure:
            self.cookie[self.__sid]['Secure'] = True

    def header(self, headers: Optional[Union[Headers, Response]] = None):
        """Generates cookie headers and appends them to headers if set.

        Returns a list of cookie header pairs.

        headers
            The object used to write the header directly.
        """
        self.write()
        cookies = self.cookie.output().split('\r\n')
        retval = []
        for cookie in cookies:
            var = cookie[:10]   # Set-Cookie
            val = cookie[12:]   # SID=###; expires=###; Path=/
            retval.append((var, val))
            if headers:
                headers.add_header(var, val)
        return retval
