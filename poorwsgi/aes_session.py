"""AES-CTR encrypted self-contained session cookie.

:Classes: AESSession

Requires the ``pyaes`` package::

    pip install pyaes
"""
import hmac
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256, sha3_256
from http.cookies import SimpleCookie
from json import dumps, loads
from logging import getLogger
from os import urandom
from typing import Any, Dict, Optional, Union

from pyaes import (  # type: ignore[import-untyped]
    AESModeOfOperationCTR, Counter)

from poorwsgi.session import Session, SessionError

log = getLogger("poorwsgi")

# pylint: disable=too-many-arguments
# pylint: disable=duplicate-code

_NONCE_SIZE = 16  # bytes — full AES block, counter state is 128 bits


class AESSession(Session):
    """Self-contained session cookie encrypted with AES-CTR.

    A drop-in replacement for ``PoorSession`` that uses AES-256-CTR for
    confidentiality and HMAC-SHA256 for integrity.  Requires the ``pyaes``
    package.

    The cookie format is ``base64(nonce + ciphertext).base64(hmac-sha256)``.

    .. code:: python

        from poorwsgi.aes_session import AESSession

        sess = AESSession(app.secret_key)
        sess.data['user'] = username
        sess.write()
        sess.header(response)
    """

    def __init__(  # pylint: disable=too-many-positional-arguments
            self, secret_key: Union[str, bytes],
            expires: int = 0,
            max_age: Optional[int] = None,
            domain: str = '',
            path: str = '/',
            secure: bool = False,
            same_site: Union[str, bool] = False,
            sid: str = 'SESSID'):
        """Constructor.

        Arguments:
            secret_key
                Secret used for AES key derivation and HMAC signing.
            expires
                Cookie ``Expires`` time in seconds.  0 means no expiration.
            max_age
                Cookie ``Max-Age`` attribute.
            domain
                Cookie ``Domain`` attribute.
            path
                Cookie ``Path`` attribute.
            secure
                If ``True``, set the ``Secure`` cookie attribute.
            same_site
                The ``SameSite`` attribute value (``'Strict'``, ``'Lax'``,
                ``'None'``) or ``False`` to omit it.
            sid
                Cookie name.
        """
        if not secret_key:
            raise SessionError("Empty secret_key")
        if isinstance(secret_key, str):
            secret_key = secret_key.encode('utf-8')

        super().__init__(expires=expires, max_age=max_age, domain=domain,
                         path=path, secure=secure, same_site=same_site,
                         sid=sid)

        root = sha3_256(secret_key).digest()
        self.__enc_key = sha3_256(root + b'enc').digest()  # AES-256 key
        self.__mac_key = sha3_256(root + b'mac').digest()  # HMAC-SHA256 key

        self.data: Dict[Any, Any] = {}

    def load(self, cookies: Any) -> None:
        """Load and decrypt session from request cookies.

        Raises ``SessionError`` if the cookie is missing, corrupted, or the
        HMAC signature does not match.

        Cookie format: ``base64(nonce + ciphertext).base64(hmac-sha256)``.
        The 16-byte nonce is prepended to the ciphertext so each cookie uses
        a unique CTR counter, preventing nonce-reuse attacks.
        """
        if not isinstance(cookies, SimpleCookie) or self._sid not in cookies:
            return
        raw = cookies[self._sid].value
        if not raw:
            return

        try:
            payload, signature = raw.encode('utf-8').split(b'.')
            payload = urlsafe_b64decode(payload)
            signature = urlsafe_b64decode(signature)

            digest = hmac.digest(self.__mac_key, payload, digest=sha256)
            if not hmac.compare_digest(digest, signature):
                raise RuntimeError("Invalid Signature")

            if len(payload) < _NONCE_SIZE:
                raise RuntimeError("Bad payload")

            nonce = payload[:_NONCE_SIZE]
            ciphertext = payload[_NONCE_SIZE:]
            counter = Counter(initial_value=int.from_bytes(nonce, 'big'))
            aes = AESModeOfOperationCTR(self.__enc_key, counter=counter)
            self.data = loads(aes.decrypt(ciphertext).decode('utf-8'))
        except Exception as err:
            log.info(repr(err))
            raise SessionError("Bad session data.") from err

        if not isinstance(self.data, dict):
            raise SessionError("Cookie data is not dictionary!")

    def write(self) -> str:
        """Encrypt session data and store it in the cookie.

        A fresh 16-byte random nonce is generated for every write so the CTR
        counter is never reused, even when the session data is unchanged.
        Format: ``base64(nonce + ciphertext).base64(hmac-sha256(...))``.
        """
        nonce = urandom(_NONCE_SIZE)
        counter = Counter(initial_value=int.from_bytes(nonce, 'big'))
        aes = AESModeOfOperationCTR(self.__enc_key, counter=counter)
        ciphertext = aes.encrypt(dumps(self.data))
        payload = nonce + ciphertext
        digest = hmac.digest(self.__mac_key, payload, digest=sha256)
        raw = urlsafe_b64encode(payload) + b'.' + urlsafe_b64encode(digest)

        value = raw.decode('utf-8')
        self.cookie[self._sid] = value
        self._apply_cookie_attrs()
        return value
