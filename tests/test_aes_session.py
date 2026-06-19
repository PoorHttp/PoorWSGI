"""Unit tests for AESSession class."""
import hmac as _hmac
from base64 import urlsafe_b64encode
from hashlib import sha256, sha3_256
from json import dumps
from os import urandom
from http.cookies import SimpleCookie

from pyaes import (  # type: ignore[import-untyped]
    AESModeOfOperationCTR, Counter)
from pytest import fixture, raises

from poorwsgi.aes_session import AESSession, _NONCE_SIZE
from poorwsgi.session import Session, SessionError

SECRET_KEY = urandom(32)

# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods


@fixture
def session_with_data():
    """AESSession instance with data written into cookie."""
    session = AESSession(SECRET_KEY)
    session.data['test'] = True
    session.write()
    return session


def test_aes_session_is_subclass_of_session():
    """AESSession must inherit from Session."""
    assert issubclass(AESSession, Session)
    assert isinstance(AESSession(SECRET_KEY), Session)


class TestErrors:
    """Test exceptions."""

    def test_empty_secret_key(self):
        with raises(SessionError):
            AESSession(b"")

    def test_empty_string_secret_key(self):
        with raises(SessionError):
            AESSession("")

    def test_same_site_invalid_raises(self):
        """Unrecognised same_site value must raise ValueError."""
        with raises(ValueError, match="is not valid"):
            AESSession(SECRET_KEY, same_site=True)

    def test_same_site_none_without_secure_raises(self):
        """same_site='None' without secure=True must raise ValueError."""
        with raises(ValueError, match="requires secure=True"):
            AESSession(SECRET_KEY, same_site="None", secure=False)

    def test_string_secret_key(self):
        """AESSession accepts a str key (encodes to bytes internally)."""
        session = AESSession("string-secret-key")
        session.data['x'] = 1
        session.write()
        session2 = AESSession("string-secret-key")
        session2.load(session.cookie)
        assert session2.data == {'x': 1}

    def test_load_missing_sid(self):
        """load() with no matching cookie name leaves data unchanged."""
        session = AESSession(SECRET_KEY)
        session.load(SimpleCookie())
        assert session.data == {}

    def test_load_empty_cookie_value(self):
        """load() with an empty cookie value leaves data unchanged."""
        cookies = SimpleCookie()
        cookies['SESSID'] = ''
        session = AESSession(SECRET_KEY)
        session.load(cookies)
        assert session.data == {}

    def test_load_short_payload(self):
        """Payload shorter than the nonce size must raise SessionError."""
        root = sha3_256(SECRET_KEY).digest()
        mac_key = sha3_256(root + b'mac').digest()
        short_payload = b'\x00' * (_NONCE_SIZE - 1)
        digest = _hmac.digest(mac_key, short_payload, digest=sha256)
        raw = (urlsafe_b64encode(short_payload)
               + b'.'
               + urlsafe_b64encode(digest))
        cookies = SimpleCookie()
        cookies['SESSID'] = raw.decode()
        session = AESSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_load_non_dict_data(self):
        """Non-dict cookie data must raise SessionError."""
        root = sha3_256(SECRET_KEY).digest()
        enc_key = sha3_256(root + b'enc').digest()
        mac_key = sha3_256(root + b'mac').digest()
        nonce = urandom(_NONCE_SIZE)
        counter = Counter(initial_value=int.from_bytes(nonce, 'big'))
        aes = AESModeOfOperationCTR(enc_key, counter=counter)
        ciphertext = aes.encrypt(dumps([1, 2, 3]))
        payload = nonce + ciphertext
        digest = _hmac.digest(mac_key, payload, digest=sha256)
        raw = urlsafe_b64encode(payload) + b'.' + urlsafe_b64encode(digest)
        cookies = SimpleCookie()
        cookies['SESSID'] = raw.decode()
        session = AESSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_bad_session_data(self):
        cookies = SimpleCookie()
        cookies["SESSID"] = "notvalidbase64!!!"
        session = AESSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_tampered_signature(self):
        """Cookie with valid structure but wrong HMAC must be rejected."""
        session = AESSession(SECRET_KEY)
        session.data['x'] = 1
        session.write()
        raw = session.cookie["SESSID"].value
        # flip last char of signature part
        parts = raw.rsplit('.', 1)
        last = 'A' if parts[1][-1] != 'A' else 'B'
        tampered = parts[0] + '.' + parts[1][:-1] + last
        cookies = SimpleCookie()
        cookies["SESSID"] = tampered
        new_session = AESSession(SECRET_KEY)
        with raises(SessionError):
            new_session.load(cookies)


class TestLoadWrite:
    """Tests of load and write methods."""

    def test_write_returns_str(self):
        session = AESSession(SECRET_KEY)
        result = session.write()
        assert isinstance(result, str)

    def test_write_load_roundtrip(self, session_with_data):
        new_session = AESSession(SECRET_KEY)
        new_session.load(session_with_data.cookie)
        assert new_session.data == {'test': True}

    def test_nonce_uniqueness(self):
        """Two write() calls for same data must produce different cookies."""
        session = AESSession(SECRET_KEY)
        session.data = {'user': 'alice'}
        raw1 = session.write()
        raw2 = session.write()
        assert raw1 != raw2

    def test_write_load_complex_data(self):
        session = AESSession(SECRET_KEY)
        session.data = {'user': 'alice', 'role': 'admin', 'count': 42}
        session.write()
        new_session = AESSession(SECRET_KEY)
        new_session.load(session.cookie)
        expected = {'user': 'alice', 'role': 'admin', 'count': 42}
        assert new_session.data == expected

    def test_wrong_key_raises(self, session_with_data):
        """Session encrypted with one key cannot be read with another."""
        new_session = AESSession(urandom(32))
        with raises(SessionError):
            new_session.load(session_with_data.cookie)
