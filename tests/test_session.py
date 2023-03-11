"""Unit tests for the PoorSession class."""
from os import urandom
from sys import version_info
from http.cookies import SimpleCookie, Morsel
from typing import Any

from pytest import fixture, raises, mark

from poorwsgi.session import PoorSession, SessionError

SECRET_KEY = urandom(32)

# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods


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


class TestSession:
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


@mark.skipif(version_info.minor < 8,
             reason="SameSite is supported from Python 3.8")
class TestSameSite:
    """Tests for the PoorSession same_site option."""

    # pylint: disable=no-self-use

    def test_default(self):
        """Tests the default SameSite behavior of PoorSession."""
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; SameSite" not in headers[0][1]

    def test_none(self):
        """Tests PoorSession with SameSite set to 'None'."""
        session = PoorSession(SECRET_KEY, same_site="None")
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
