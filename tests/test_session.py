from os import urandom
from sys import version_info
from http.cookies import SimpleCookie

from pytest import fixture, raises, mark

from poorwsgi.session import PoorSession, SessionError


class Request:
    secret_key = urandom(32)
    cookies = SimpleCookie()


class Empty:
    secret_key = None


@fixture
def req():
    return Request()


class TestSession:
    def test_default(self, req):
        session = PoorSession(req)
        headers = session.header()
        assert "Expires" not in headers[0][1]
        assert "Max-Age" not in headers[0][1]
        assert "Path" in headers[0][1]
        assert "Domain" not in headers[0][1]

    def test_destroy(self, req):
        session = PoorSession(req)
        session.destroy()
        headers = session.header()
        assert "; expires=" in headers[0][1]

    def test_expires(self, req):
        session = PoorSession(req, expires=10)
        headers = session.header()
        assert "; expires=" in headers[0][1]

    def test_max_age(self, req):
        session = PoorSession(req, max_age=10)
        headers = session.header()
        assert "; Max-Age=10;" in headers[0][1]

    def test_no_path(self, req):
        session = PoorSession(req, path=None)
        headers = session.header()
        assert "Path" not in headers[0][1]

    def test_domain(self, req):
        session = PoorSession(req, domain="example.org")
        headers = session.header()
        assert "; Domain=example.org; " in headers[0][1]

    def test_httponly(self, req):
        session = PoorSession(req)
        headers = session.header()
        assert "; HttpOnly; " in headers[0][1]

    def test_http(self, req):
        session = PoorSession(req)
        headers = session.header()
        assert "; Secure" not in headers[0][1]

    def test_https(self, req):
        session = PoorSession(req, secure=True)
        headers = session.header()
        assert "; Secure" in headers[0][1]


@mark.skipif(version_info.minor < 8,
             reason="SameSite is supported from Python 3.8")
class TestSameSite:
    def test_default(self, req):
        session = PoorSession(req)
        headers = session.header()
        assert "; SameSite" not in headers[0][1]

    def test_none(self, req):
        session = PoorSession(req, same_site="None")
        headers = session.header()
        assert "; SameSite=None" in headers[0][1]

    def test_lax(self, req):
        session = PoorSession(req, same_site="Lax")
        headers = session.header()
        assert "; SameSite=Lax" in headers[0][1]

    def test_strict(self, req):
        session = PoorSession(req, same_site="Strict")
        headers = session.header()
        assert "; SameSite=Strict" in headers[0][1]


class TestErrors:
    def test_no_secret_key(self):
        with raises(SessionError):
            PoorSession(Empty)

    def test_bad_session(self, req):
        req.cookies = SimpleCookie()
        req.cookies["SESSID"] = "\0"

        with raises(SessionError):
            PoorSession(req)
