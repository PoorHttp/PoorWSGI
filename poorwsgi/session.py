"""PoorSession self-contained cookie class.

:Classes: PoorSession
:Functions: get_token, check_token

This module is depended to pyaes https://pypi.org/project/pyaes/
"""
import hmac
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256, sha3_256
from http.cookies import SimpleCookie
from json import dumps, loads
from logging import getLogger
from time import time
from typing import Any, Dict, Optional, Union

from pyaes import AESModeOfOperationCTR  # type: ignore

from poorwsgi.headers import Headers
from poorwsgi.response import Response

log = getLogger("poorwsgi")  # pylint: disable=invalid-name

# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes
# pylint: disable=unsubscriptable-object
# pylint: disable=consider-using-f-string


def get_token(secret: str,
              client: str,
              timeout: Optional[int] = None,
              expired: int = 0):
    """Create token from secret, and client string.

    If timeout is set, token contains time align with twice of this value.
    Twice, because time of creating can be so near to computed time.
    """
    if timeout is None:
        text = "%s%s" % (secret, client)
    else:
        if expired == 0:
            now = int(time() / timeout) * timeout  # shift to start time
            expired = now + 2 * timeout
        text = "%s%s%s" % (secret, expired, client)

    return sha256(text.encode()).hexdigest()


def check_token(token: str,
                secret: str,
                client: str,
                timeout: Optional[int] = None):
    """Check token, if it is right.

    Arguments secret, client and expired must be same, when token was
    generated. If expired is set, than token must be younger than 2*expired.
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
    """Base Exception for Session"""


class PoorSession:
    """Self-contained cookie with session data.

    You cat store or read data from object via PoorSession.data variable which
    must be dictionary. Data is stored to cookie by json dump, and next encrypt
    with by AES CTR method with `secret_key`. Session data are signed just like
    JWT.

    .. code:: python

        sess = PoorSession(app.secret_key)

        sess.data['class'] = obj.__class__          # write to cookie
        sess.data['dict'] = obj.__dict__.copy()

        obj = sess.data['class']()                  # read from cookie
        obj.__dict__ = sess.data['dict'].copy()

    Or for beter solution, you can create export and import methods for you
    object like that:

    .. code:: python

        class Obj(object):
            def import(self, d):
                self.attr1 = d['attr1']
                self.attr2 = d['attr2']

            def export(self):
                d = {'attr1': self.attr1, 'attr2': self.attr2}
                return d

        obj = Obj()
        sess = PoorSession(app.secret_key)

        sess.data['class'] = obj.__class__          # write to cookie
        sess.data['dict'] = obj.export()

        obj = sess.data['class']()                  # read from cookie
        obj.import(sess.data['dict'])
    """

    def __init__(self,
                 secret_key: Union[str, bytes],
                 expires: int = 0,
                 max_age: Optional[int] = None,
                 domain: str = '',
                 path: str = '/',
                 secure: bool = False,
                 same_site: bool = False,
                 sid: str = 'SESSID'):
        """Constructor.

        Arguments:
            expires : int
                Cookie ``Expires`` time in seconds, if it 0, no expire is set
            max_age : int
                Cookie ``Max-Age`` attribute. If both expires and max-age are
                set, max_age has precedence.
            domain : str
                Cookie ``Host`` to which the cookie will be sent.
            path : str
                Cookie ``Path`` that must exist in the requested URL.
            secure : bool
                If ``Secure`` cookie attribute will be sent.
            same_site: str
                The ``SameSite`` attribute. When is set could be one of
                ``Strict|Lax|None``. By default attribute is not set which is
                ``Lax`` by browser.
            sid : str
                Cookie key name.

        .. code:: Python

            session_config = {
                'expires': 3600,  # one hour
                'max_age': 3600,
                'domain': 'example.net',
                'path': '/application',
                ̈́'secure': True,
                'same_site': True,
                'sid': 'MYSID'
            }

            session = PostSession(app.secret_key, **config)
            try:
                session.load(req.cookies)
            except SessionError as err:
                log.error("Invalid session: %s", str(err))

        *Changed in version 2.4.x*: use app.secret_key in constructor, and than
        call load method.

        *Changed in version 2.7.0*:
            * Using AES encryption with signature just like in JWT.
            * Removing compression
            * Use secret key have to be string or bytes.
        """
        if not secret_key:
            raise SessionError("Empty secret_key")
        if isinstance(secret_key, str):
            secret_key = secret_key.encode('utf-8')

        self.__secret_key = sha3_256(secret_key).digest()
        self.__sid = sid
        self.__expires = expires
        self.__max_age = max_age
        self.__domain = domain
        self.__path = path
        self.__secure = secure
        self.__same_site = same_site

        # data is session dictionary to store user data in cookie
        self.data: Dict[Any, Any] = {}
        self.cookie: SimpleCookie = SimpleCookie()
        self.cookie[sid] = ''

    def load(self, cookies: Optional[SimpleCookie]):
        """Load session from request's cookie"""
        if not isinstance(cookies, SimpleCookie) or self.__sid not in cookies:
            return
        raw = cookies[self.__sid].value

        if not raw:
            return

        try:
            # payload, signature = map(urlsafe_b64decode,
            #                          raw.encode('utf-8').split(b'.'))
            payload, signature = raw.encode('utf-8').split(b'.')
            payload = urlsafe_b64decode(payload)
            signature = urlsafe_b64decode(signature)

            digest = hmac.digest(self.__secret_key, payload, digest=sha256)
            if not hmac.compare_digest(digest, signature):
                raise RuntimeError("Invalid Signature")

            aes = AESModeOfOperationCTR(self.__secret_key)
            self.data = loads(aes.decrypt(payload).decode('utf-8'))

        except Exception as err:
            log.info(repr(err))
            raise SessionError("Bad session data.") from err

        if not isinstance(self.data, dict):
            raise SessionError("Cookie data is not dictionary!")

    def write(self):
        """Store data to cookie value.

        This method is called automatically in header method.
        """
        aes = AESModeOfOperationCTR(self.__secret_key)
        payload = aes.encrypt(dumps(self.data))
        digest = hmac.digest(self.__secret_key, payload, digest=sha256)
        raw = urlsafe_b64encode(payload) + b'.' + urlsafe_b64encode(digest)

        self.cookie[self.__sid] = raw.decode('utf-8')
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
        """Destroy session. In fact, set cookie expires value to past (-1).

        Be sure, that data can't be changed:
        https://stackoverflow.com/a/5285982/8379994
        """
        self.cookie[self.__sid]['expires'] = -1
        if self.__max_age is not None:
            self.cookie[self.__sid]['Max-Age'] = -1
        self.cookie[self.__sid]['HttpOnly'] = True
        if self.__secure:
            self.cookie[self.__sid]['Secure'] = True

    def header(self, headers: Optional[Union[Headers, Response]] = None):
        """Generate cookie headers and append it to headers if it set.

        Returns list of cookie header pairs.

        headers : Headers or Response
            Object, which is used to write header directly.
        """
        self.write()
        cookies = self.cookie.output().split('\r\n')
        retval = []
        for cookie in cookies:
            var = cookie[:10]  # Set-Cookie
            val = cookie[12:]  # SID=###; expires=###; Path=/
            retval.append((var, val))
            if headers:
                headers.add_header(var, val)
        return retval
