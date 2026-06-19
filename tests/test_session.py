"""Unit tests for Session and PoorSession classes."""
import bz2
import hmac as _hmac
from base64 import b64encode
from hashlib import shake_256
from os import urandom
from http.cookies import SimpleCookie, Morsel
from json import dumps
from random import Random
from time import time as _time
from typing import Any

from pytest import fixture, raises

from poorwsgi.session import (
    Session, PoorSession, SessionError, NoCompress,
    get_token, check_token, hidden, encrypt, KEYSTREAM_SIZE,
)

SECRET_KEY = urandom(32)

# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods


def _make_poor_cookie(key: bytes, data) -> str:
    """Build a PoorSession-compatible cookie with arbitrary (possibly non-dict)
    data so we can craft edge-case payloads in tests."""
    secret_hash = shake_256(b'ks\x00' + key).digest(KEYSTREAM_SIZE)
    mac_key = shake_256(b'mac\x00' + key).digest(32)
    table = bytearray(range(256))
    perm_seed = shake_256(b'perm\x00' + key).digest(32)
    Random(perm_seed).shuffle(table)  # nosec # noqa: S311
    payload = bz2.compress(
        encrypt(hidden(dumps(data), secret_hash), table), 9)
    sig = _hmac.digest(mac_key, payload, 'sha256')
    return b64encode(payload).decode() + '.' + b64encode(sig).decode()


class MockHeaders:
    """Minimal stand-in for Headers/Response that records add_header calls."""
    def __init__(self):
        self.headers = []

    def add_header(self, name, value):
        self.headers.append((name, value))


class Request:
    """A mock Request class."""
    secret_key = SECRET_KEY
    cookies: Any = SimpleCookie()


class Empty:
    """A mock Request class without a secret key."""
    secret_key = None


@fixture
def req():
    """An instance of a Request object."""
    return Request()


@fixture
def req_session():
    """An instance of a Request object with a session cookie."""
    request = Request()
    session = PoorSession(request.secret_key)
    session.data['test'] = True
    session.write()
    request.cookies = session.cookie
    return request


class TestNoCompress:
    """Tests for the NoCompress pass-through class."""

    # pylint: disable=no-self-use

    def test_compress_returns_data_unchanged(self):
        data = b"hello world"
        assert NoCompress.compress(data) == data

    def test_decompress_returns_data_unchanged(self):
        data = b"hello world"
        assert NoCompress.decompress(data) == data


class TestTokens:
    """Tests for get_token and check_token helper functions."""

    # pylint: disable=no-self-use

    def test_get_token_without_timeout(self):
        token = get_token("secret", "client")
        assert isinstance(token, str)
        assert len(token) == 64  # sha3_256 hex digest

    def test_get_token_is_deterministic(self):
        assert get_token("secret", "client") == get_token("secret", "client")

    def test_get_token_with_timeout(self):
        token = get_token("secret", "client", timeout=300)
        assert isinstance(token, str)
        assert len(token) == 64

    def test_get_token_with_explicit_expired(self):
        token = get_token("secret", "client", timeout=300, expired=9999999999)
        assert isinstance(token, str)

    def test_check_token_without_timeout_valid(self):
        token = get_token("secret", "client")
        assert check_token(token, "secret", "client") is True

    def test_check_token_without_timeout_invalid(self):
        assert check_token("badtoken", "secret", "client") is False

    def test_check_token_with_timeout_valid(self):
        token = get_token("secret", "client", timeout=300)
        assert check_token(token, "secret", "client", timeout=300) is True

    def test_check_token_with_timeout_first_window_match(self):
        """check_token must return True on first window match (covers early
        return branch)."""
        timeout = 300
        now = int(_time() / timeout) * timeout
        # check_token tries expired = now + timeout first
        token = get_token("secret", "client", timeout=timeout,
                          expired=now + timeout)
        assert check_token(token, "secret", "client", timeout=timeout) is True

    def test_check_token_with_timeout_invalid(self):
        assert check_token(
            "badtoken", "secret", "client", timeout=300) is False


class TestPoorSession:
    """Tests PoorSession configuration options."""

    # pylint: disable=no-self-use

    def test_default(self):
        """Tests the default PoorSession configuration."""
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "Expires" not in headers[0][1]
        assert "Max-Age" not in headers[0][1]
        assert "Path" in headers[0][1]
        assert "Domain" not in headers[0][1]

    def test_destroy(self):
        """Tests the destroy method of PoorSession."""
        session = PoorSession(SECRET_KEY)
        session.destroy()
        headers = session.header()
        assert "; expires=" in headers[0][1]

    def test_expires(self):
        """Tests PoorSession with an expires setting."""
        session = PoorSession(SECRET_KEY, expires=10)
        headers = session.header()
        assert "; expires=" in headers[0][1]

    def test_max_age(self):
        """Tests PoorSession with a max_age setting."""
        session = PoorSession(SECRET_KEY, max_age=10)
        headers = session.header()
        assert "; Max-Age=10;" in headers[0][1]

    def test_no_path(self):
        """Tests PoorSession when no path is specified."""
        session = PoorSession(SECRET_KEY, path=None)
        headers = session.header()
        assert "Path" not in headers[0][1]

    def test_domain(self):
        """Tests PoorSession with a specified domain."""
        session = PoorSession(SECRET_KEY, domain="example.org")
        headers = session.header()
        assert "; Domain=example.org; " in headers[0][1]

    def test_httponly(self):
        """Tests PoorSession with HttpOnly attribute."""
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; HttpOnly; " in headers[0][1]

    def test_http(self):
        """Tests PoorSession without a secure setting (HTTP)."""
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; Secure" not in headers[0][1]

    def test_https(self):
        """Tests PoorSession with a secure setting (HTTPS)."""
        session = PoorSession(SECRET_KEY, secure=True)
        headers = session.header()
        assert "; Secure" in headers[0][1]

    def test_load_empty_cookie(self):
        """Tests that load() with an empty SimpleCookie leaves data as {}."""
        session = PoorSession(SECRET_KEY)
        session.load(SimpleCookie())
        assert session.data == {}

    def test_load_missing_sid(self):
        """Tests that load() with a cookie that has no matching SID leaves
        data as {}."""
        cookies = SimpleCookie()
        cookies["OTHER"] = "value"
        session = PoorSession(SECRET_KEY)
        session.load(cookies)
        assert session.data == {}


class TestSameSite:
    """Tests for the PoorSession same_site option."""

    # pylint: disable=no-self-use

    def test_default(self):
        """Tests the default SameSite behavior of PoorSession."""
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; SameSite" not in headers[0][1]

    def test_none(self):
        """Tests PoorSession with SameSite='None' (requires secure=True)."""
        session = PoorSession(SECRET_KEY, same_site="None", secure=True)
        headers = session.header()
        assert "; SameSite=None" in headers[0][1]

    def test_lax(self):
        """Tests PoorSession with SameSite set to 'Lax'."""
        session = PoorSession(SECRET_KEY, same_site="Lax")
        headers = session.header()
        assert "; SameSite=Lax" in headers[0][1]

    def test_strict(self):
        """Tests PoorSession with SameSite set to 'Strict'."""
        session = PoorSession(SECRET_KEY, same_site="Strict")
        headers = session.header()
        assert "; SameSite=Strict" in headers[0][1]

    def test_invalid_value_raises(self):
        """Unrecognised same_site value must raise ValueError."""
        with raises(ValueError, match="is not valid"):
            PoorSession(SECRET_KEY, same_site=True)

    def test_none_without_secure_raises(self):
        """same_site='None' without secure=True must raise ValueError."""
        with raises(ValueError, match="requires secure=True"):
            PoorSession(SECRET_KEY, same_site="None", secure=False)


class TestErrors:
    """Tests exceptions."""

    # pylint: disable=no-self-use

    def test_no_secret_key(self):
        """Tests PoorSession initialization without a secret key, expecting
        SessionError."""
        with raises(SessionError):
            PoorSession(Empty)

    def test_bad_session(self):
        """Tests loading a bad session cookie, expecting SessionError."""
        # pylint: disable=protected-access
        cookies = SimpleCookie()
        morsel = Morsel()
        morsel._key = 'SESSID'
        morsel._value = '\0'
        morsel._coded_value = '"\\000"'
        cookies['SESSID'] = morsel
        session = PoorSession(SECRET_KEY)

        with raises(SessionError):
            session.load(cookies)

    def test_string_secret_key(self):
        """PoorSession accepts a str key (encodes to bytes internally)."""
        session = PoorSession("string-secret-key")
        session.data['x'] = 1
        session.write()
        session2 = PoorSession("string-secret-key")
        session2.load(session.cookie)
        assert session2.data == {'x': 1}

    def test_load_empty_cookie_value(self):
        """load() with an empty cookie value leaves data unchanged."""
        cookies = SimpleCookie()
        cookies['SESSID'] = ''
        session = PoorSession(SECRET_KEY)
        session.load(cookies)
        assert session.data == {}

    def test_load_no_dot_separator(self):
        """Cookie without a '.' separator must raise SessionError."""
        cookies = SimpleCookie()
        cookies['SESSID'] = b64encode(b'nodot').decode()
        session = PoorSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_load_short_signature(self):
        """Cookie with a signature shorter than 32 bytes must raise
        SessionError."""
        payload = b64encode(b'somepayload').decode()
        sig = b64encode(b'short').decode()
        cookies = SimpleCookie()
        cookies['SESSID'] = f'{payload}.{sig}'
        session = PoorSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_load_non_dict_data(self):
        """Non-dict cookie data must raise SessionError."""
        cookies = SimpleCookie()
        cookies['SESSID'] = _make_poor_cookie(SECRET_KEY, [1, 2, 3])
        session = PoorSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_bad_session_compatibility(self, req):
        """Tests PoorSession compatibility with a bad session cookie, expecting
        SessionError."""
        # pylint: disable=protected-access
        req.cookies = SimpleCookie()
        morsel = Morsel()
        morsel._key = 'SESSID'
        morsel._value = '\0'
        morsel._coded_value = '"\\000"'
        req.cookies['SESSID'] = morsel

        with raises(SessionError):
            PoorSession(req)


class TestLoadWrite:
    """Tests the load and write methods."""

    # pylint: disable=no-self-use

    def test_compatibility_empty(self, req):
        """Tests compatibility with an empty request in PoorSession
        constructor."""
        session = PoorSession(req)
        assert session.data == {}

    def test_compatibility(self, req_session):
        """Tests compatibility with a session cookie in PoorSession
        constructor."""
        session = PoorSession(req_session)
        assert session.data == {'test': True}

    def test_write_load(self, req_session):
        """Tests the write and load methods of PoorSession."""
        session = PoorSession(SECRET_KEY)
        session.load(req_session.cookies)
        assert session.data == {'test': True}

    def test_tampered_cookie_rejected(self, req_session):
        """Tests that a tampered cookie value raises SessionError."""
        # Flip one byte in the payload part (before the '.')
        raw = req_session.cookies['SESSID'].value
        payload_b64, sig_b64 = raw.split('.')
        # Replace last char of payload to corrupt the ciphertext
        corrupted = payload_b64[:-1] + ('A' if payload_b64[-1] != 'A' else 'B')
        # Rebuild cookie with original signature — HMAC must reject it
        # pylint: disable=protected-access
        morsel = Morsel()
        morsel._key = 'SESSID'
        morsel._value = corrupted + '.' + sig_b64
        morsel._coded_value = corrupted + '.' + sig_b64
        req_session.cookies['SESSID'] = morsel

        session = PoorSession(SECRET_KEY)
        with raises(SessionError):
            session.load(req_session.cookies)

    def test_wrong_key_rejected(self, req_session):
        """Tests that a cookie encrypted with a different key raises
        SessionError."""
        session = PoorSession(b'different_key_' + SECRET_KEY)
        with raises(SessionError):
            session.load(req_session.cookies)


class TestSession:
    """Tests for the plain Session base class."""

    # pylint: disable=no-self-use

    def test_default(self):
        """Tests default Session cookie attributes."""
        session = Session()
        headers = session.header()
        assert "HttpOnly" in headers[0][1]
        assert "Path=/" in headers[0][1]
        assert "Expires" not in headers[0][1]
        assert "Max-Age" not in headers[0][1]
        assert "Domain" not in headers[0][1]
        assert "Secure" not in headers[0][1]

    def test_load_write(self):
        """Tests that a value written by Session can be read back."""
        session = Session()
        session.data = "my-session-id"
        session.write()

        session2 = Session()
        session2.load(session.cookie)
        assert session2.data == "my-session-id"

    def test_empty_cookie(self):
        """Tests that Session.load with no matching cookie leaves data as
        empty string."""
        session = Session()
        session.load(SimpleCookie())
        assert session.data == ""

    def test_destroy(self):
        """Tests that destroy sets expires in the past."""
        session = Session()
        session.destroy()
        headers = session.header()
        assert "expires=" in headers[0][1]

    def test_destroy_with_max_age(self):
        """destroy() must also set Max-Age=-1 when max_age was configured."""
        session = Session(max_age=3600)
        session.destroy()
        headers = session.header()
        assert "Max-Age=-1" in headers[0][1]
        assert "Max-Age=3600" not in headers[0][1]

    def test_destroy_with_secure(self):
        """destroy() must preserve the Secure flag when configured."""
        session = Session(secure=True)
        session.destroy()
        headers = session.header()
        assert "Secure" in headers[0][1]

    def test_header_writes_to_headers_object(self):
        """header(obj) must call obj.add_header() for each cookie header."""
        session = Session()
        session.data = "tok"
        mock = MockHeaders()
        returned = session.header(mock)
        assert len(mock.headers) == len(returned)
        assert mock.headers == returned

    def test_expires(self):
        """Tests Session with an expires setting."""
        session = Session(expires=3600)
        headers = session.header()
        assert "expires=" in headers[0][1]

    def test_max_age(self):
        """Tests Session with a max_age setting."""
        session = Session(max_age=3600)
        headers = session.header()
        assert "Max-Age=3600" in headers[0][1]

    def test_secure(self):
        """Tests Session with secure=True."""
        session = Session(secure=True)
        headers = session.header()
        assert "Secure" in headers[0][1]

    def test_same_site(self):
        """Tests Session with same_site='Strict'."""
        session = Session(same_site="Strict")
        headers = session.header()
        assert "SameSite=Strict" in headers[0][1]

    def test_same_site_invalid_raises(self):
        """Unrecognised same_site value must raise ValueError."""
        with raises(ValueError, match="is not valid"):
            Session(same_site=True)

    def test_same_site_none_without_secure_raises(self):
        """same_site='None' without secure=True must raise ValueError."""
        with raises(ValueError, match="requires secure=True"):
            Session(same_site="None", secure=False)

    def test_custom_sid(self):
        """Tests Session with a custom cookie name."""
        session = Session(sid="MYSESSID")
        session.data = "token-value"
        session.write()
        assert "MYSESSID" in session.cookie

    def test_is_base_of_poor_session(self):
        """Tests that PoorSession is a subclass of Session."""
        assert issubclass(PoorSession, Session)
        assert isinstance(PoorSession(SECRET_KEY), Session)
