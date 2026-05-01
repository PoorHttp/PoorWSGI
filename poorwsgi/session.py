"""Session cookie classes.

:Classes:   NoCompress, Session, PoorSession
:Functions: hidden, encrypt, decrypt, get_token, check_token

:class:`Session` is a plain cookie wrapper suitable for storing a server-side
session ID or a JWT.  No encryption is applied; the value is stored verbatim.

:class:`PoorSession` is a self-contained encrypted session cookie.

Cookie format for PoorSession: ``base64(ciphertext).base64(hmac-sha256)``

Security note: PoorSession uses a custom XOR + byte-substitution cipher with
HMAC-SHA256 authentication. The keystream is derived deterministically from
the secret key (no per-message nonce), which makes it vulnerable to
known-plaintext attacks given enough collected cookies. It is suitable as a
"no external dependencies" baseline. For stronger confidentiality use the
``cryptography`` package variant.
"""
import bz2
import hmac
from base64 import b64decode, b64encode
from hashlib import sha3_256, shake_256
from json import dumps, loads
from logging import getLogger
from random import Random
from time import time
from typing import Any, Dict, Optional, Union

from http.cookies import SimpleCookie

from poorwsgi.headers import Headers
from poorwsgi.response import Response

# Length of the XOR keystream derived from the secret key.  Longer values
# reduce the risk of known-plaintext reconstruction: an attacker needs roughly
# KEYSTREAM_SIZE / (known bytes per cookie) cookies to reconstruct the stream.
# Must be a positive integer; changing it invalidates all existing cookies.
KEYSTREAM_SIZE = 1024

log = getLogger("poorwsgi")  # pylint: disable=invalid-name

# pylint: disable=unsubscriptable-object
# pylint: disable=consider-using-f-string


def hidden(text: Union[str, bytes], secret_hash: bytes) -> bytes:
    """(En|de)crypts text with a SHA hash of the password via XOR.

    text
        Raw data to (en|de)crypt.
    secret_hash
        Binary digest of the secret key.
    """
    secret_len = len(secret_hash)

    # text must be bytes
    if isinstance(text, str):
        text = text.encode("utf-8")

    retval = bytearray()
    for i, val in enumerate(text):
        retval.append(val ^ secret_hash[i % secret_len])

    return retval


def encrypt(data: bytes, table: bytearray) -> bytes:
    """Encrypt data by replacing bytes value.

    >>> encrypt(b'Hello', bytearray(range(255, -1, -1)))
    b'\xb7\x9a\x93\x93\x90'
    """
    return bytes(table[byte] for byte in data)


def decrypt(data: bytes, table: bytearray) -> bytes:
    """Decrypt data by replacing bytes value.

    >>> decrypt(b'\\xb7\\x9a\\x93\\x93\\x90', bytearray(range(255, -1, -1)))
    b'Hello'
    """
    reverse = {}
    for key, val in enumerate(table):
        reverse[val] = key
    return bytes(reverse[byte] for byte in data)


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

    return sha3_256(text.encode()).hexdigest()


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


class Session:
    """Simple cookie session — stores a single raw string value.

    Suitable for holding a server-side session ID or a JWT.  No encryption
    or integrity protection is applied; the value is stored in the cookie
    verbatim.  When storing a JWT, integrity and authenticity are provided by
    the JWT itself.  When storing a server-side session ID, security comes
    from the server-side store.

    The cookie is always set with ``HttpOnly=True``.  Use ``secure=True``
    when serving over HTTPS.

    This class is also the base class for :class:`PoorSession`.

    .. code:: python

        session = Session(secure=True)
        session.load(req.cookies)

        if not session.data:            # no active session
            session.data = create_server_session(req)

        resp = Response(...)
        session.header(resp)

    """

    def __init__(self, expires: int = 0, max_age: Optional[int] = None,
                 domain: str = '', path: str = '/', secure: bool = False,
                 same_site: Union[str, bool] = False, sid: str = 'SESSID'):
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
            sid
                The cookie key name.
        """
        self._sid = sid
        self.__expires = expires
        self.__max_age = max_age
        self.__domain = domain
        self.__path = path
        self.__secure = secure
        self.__same_site = same_site

        self.data: Any = ""
        self.cookie: SimpleCookie = SimpleCookie()
        self.cookie[sid] = ''

    def _apply_cookie_attrs(self):
        """Apply security and configuration attributes to the session cookie.

        Called by :meth:`write` and subclass overrides of :meth:`write`.
        Sets ``HttpOnly``, ``Domain``, ``Path``, ``Secure``, ``SameSite``,
        ``Expires``, and ``Max-Age`` as configured.
        """
        self.cookie[self._sid]['HttpOnly'] = True
        if self.__domain:
            self.cookie[self._sid]['Domain'] = self.__domain
        if self.__path:
            self.cookie[self._sid]['path'] = self.__path
        if self.__secure:
            self.cookie[self._sid]['Secure'] = True
        if self.__same_site:
            self.cookie[self._sid]['SameSite'] = self.__same_site
        if self.__expires:
            self.cookie[self._sid]['expires'] = self.__expires
        if self.__max_age is not None:
            self.cookie[self._sid]['Max-Age'] = self.__max_age

    def load(self, cookies: Optional[SimpleCookie]):
        """Load the session value from the request's cookies.

        Sets :attr:`data` to the raw cookie string, or leaves it as ``""``
        if the cookie is absent or empty.
        """
        if not isinstance(cookies, SimpleCookie) or self._sid not in cookies:
            return
        self.data = cookies[self._sid].value

    def write(self) -> str:
        """Store :attr:`data` to the cookie value.

        This method is called automatically by :meth:`header`.
        Returns the raw string written to the cookie.
        """
        raw = self.data if isinstance(self.data, str) else str(self.data)
        self.cookie[self._sid] = raw
        self._apply_cookie_attrs()
        return raw

    def destroy(self):
        """Destroy the session by setting the cookie's expires to the past
        (-1).

        Ensures that data cannot be changed:
        https://stackoverflow.com/a/5285982/8379994
        """
        self.cookie[self._sid]['expires'] = -1
        if self.__max_age is not None:
            self.cookie[self._sid]['Max-Age'] = -1
        self.cookie[self._sid]['HttpOnly'] = True
        if self.__secure:
            self.cookie[self._sid]['Secure'] = True

    def header(self, headers: Optional[Union[Headers, Response]] = None):
        """Generate cookie headers and optionally append them to headers.

        Returns a list of ``(name, value)`` cookie header pairs.

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


class PoorSession(Session):
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

    def __init__(self, secret_key: Union[str, bytes],
                 expires: int = 0, max_age: Optional[int] = None,
                 domain: str = '', path: str = '/', secure: bool = False,
                 same_site: Union[str, bool] = False, compress=bz2,
                 sid: str = 'SESSID'):
        """Constructor.

        Arguments:
            secret_key
                The application secret key used for encryption and signing.
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
                'same_site': 'Strict',
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
        super().__init__(expires=expires, max_age=max_age, domain=domain,
                         path=path, secure=secure, same_site=same_site,
                         sid=sid)

        _request = None
        if not isinstance(secret_key, (str, bytes)):  # backwards compatibility
            log.warning('Do not use request in PoorSession constructor, '
                        'see new api and call load method manually.')
            _request = secret_key
            secret_key = _request.secret_key

        if isinstance(secret_key, str):
            secret_key = secret_key.encode('utf-8')

        if not secret_key:
            raise SessionError("poor_SecretKey is not set!")

        # XOR keystream — domain-separated from MAC key.
        self.__secret_hash = shake_256(b'ks\x00' + secret_key).digest(
            KEYSTREAM_SIZE)
        # MAC key — independent derivation so changing KEYSTREAM_SIZE does not
        # affect it and vice versa.
        self.__mac_key = shake_256(b'mac\x00' + secret_key).digest(32)
        # Permutation table seeded independently from its own label.
        self.__secret_table = bytearray(range(256))
        perm_seed = shake_256(b'perm\x00' + secret_key).digest(32)
        Random(perm_seed).shuffle(self.__secret_table)  # nosec  # noqa: S311

        self.__cps = compress if compress is not None else NoCompress
        self.data: Dict[Any, Any] = {}

        if _request is not None:
            self.load(_request.cookies)

    def load(self, cookies: Optional[SimpleCookie]):
        """Load and decrypt the session from the request's cookies."""
        if not isinstance(cookies, SimpleCookie) or self._sid not in cookies:
            return
        raw = cookies[self._sid].value

        if not raw:
            return

        try:
            if '.' not in raw:
                raise ValueError("Missing HMAC separator")
            payload_b64, sig_b64 = raw.split('.', 1)

            payload = b64decode(payload_b64.encode(), validate=True)
            signature = b64decode(sig_b64.encode(), validate=True)

            if len(signature) != 32:
                raise ValueError("Invalid signature length")

            expected = hmac.digest(self.__mac_key, payload, 'sha256')
            if not hmac.compare_digest(expected, signature):
                raise ValueError("Invalid signature")

            self.data = loads(
                hidden(
                    decrypt(
                        self.__cps.decompress(payload),
                        self.__secret_table),
                    self.__secret_hash))
        except Exception as err:
            log.info(repr(err))
            raise SessionError("Bad session data.") from err

        if not isinstance(self.data, dict):
            raise SessionError("Cookie data is not dictionary!")

    def write(self) -> str:
        """Encrypt and sign the session data, write to cookie.

        This method is called automatically by :meth:`header`.
        """
        payload = self.__cps.compress(
            encrypt(hidden(dumps(self.data), self.__secret_hash),
                    self.__secret_table),
            9)
        signature = hmac.digest(self.__mac_key, payload, 'sha256')
        raw = b64encode(payload).decode() + '.' + b64encode(signature).decode()
        self.cookie[self._sid] = raw
        self._apply_cookie_attrs()
        return raw
