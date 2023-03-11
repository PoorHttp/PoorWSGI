"""Unit tests for PoorSession class."""
from os import urandom
from sys import version_info
from http.cookies import SimpleCookie
from typing import Any

from pytest import fixture, raises, mark

from poorwsgi.session import PoorSession, SessionError

SECRET_KEY = urandom(32)

# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods


class Request:
    """Request mock"""
    secret_key = SECRET_KEY
    cookies: Any = SimpleCookie()


@fixture
def req():
    """Instance of Request object."""
    return Request()


@fixture
def req_session():
    """Instace of Request object with session cookie."""
    request = Request()
    session = PoorSession(request.secret_key)
    session.data['test'] = True
    session.write()
    request.cookies = session.cookie
    return request


class TestSession:
    """Test PoorSession configuration options."""
    def test_default(self):
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "Expires" not in headers[0][1]
        assert "Max-Age" not in headers[0][1]
        assert "Path" in headers[0][1]
        assert "Domain" not in headers[0][1]

    def test_destroy(self):
        session = PoorSession(SECRET_KEY)
        session.destroy()
        headers = session.header()
        assert "; expires=" in headers[0][1]

    def test_expires(self):
        session = PoorSession(SECRET_KEY, expires=10)
        headers = session.header()
        assert "; expires=" in headers[0][1]

    def test_max_age(self):
        session = PoorSession(SECRET_KEY, max_age=10)
        headers = session.header()
        assert "; Max-Age=10;" in headers[0][1]

    def test_no_path(self):
        session = PoorSession(SECRET_KEY, path=None)
        headers = session.header()
        assert "Path" not in headers[0][1]

    def test_domain(self):
        session = PoorSession(SECRET_KEY, domain="example.org")
        headers = session.header()
        assert "; Domain=example.org; " in headers[0][1]

    def test_httponly(self):
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; HttpOnly; " in headers[0][1]

    def test_http(self):
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; Secure" not in headers[0][1]

    def test_https(self):
        session = PoorSession(SECRET_KEY, secure=True)
        headers = session.header()
        assert "; Secure" in headers[0][1]


@mark.skipif(version_info.minor < 8,
             reason="SameSite is supported from Python 3.8")
class TestSameSite:
    """Test for PoorSession same_site option."""
    def test_default(self):
        session = PoorSession(SECRET_KEY)
        headers = session.header()
        assert "; SameSite" not in headers[0][1]

    def test_none(self):
        session = PoorSession(SECRET_KEY, same_site="None")
        headers = session.header()
        assert "; SameSite=None" in headers[0][1]

    def test_lax(self):
        session = PoorSession(SECRET_KEY, same_site="Lax")
        headers = session.header()
        assert "; SameSite=Lax" in headers[0][1]

    def test_strict(self):
        session = PoorSession(SECRET_KEY, same_site="Strict")
        headers = session.header()
        assert "; SameSite=Strict" in headers[0][1]


class TestErrors:
    """Test exceptions"""
    def test_no_secret_key(self):
        with raises(SessionError):
            PoorSession('')

    def test_bad_session(self):
        cookies = SimpleCookie()
        cookies["SESSID"] = "\0"
        session = PoorSession(SECRET_KEY)

        with raises(SessionError):
            session.load(cookies)


class TestLoadWrite:
    """Tests of load and write methods."""
    def test_write_load(self, req_session):
        """Method write was called in fixture req_session."""
        session = PoorSession(SECRET_KEY)
        session.load(req_session.cookies)
        assert session.data == {'test': True}
