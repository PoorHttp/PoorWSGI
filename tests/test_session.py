from os import urandom
from http.cookies import SimpleCookie

from pytest import fixture, raises

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
    def test_destroy(self, req):
        session = PoorSession(req)
        session.destroy()
        headers = session.header()
        assert "; expires=" in headers[0][1]

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


class TestErrors:
    def test_no_secret_key(self):
        with raises(SessionError):
            PoorSession(Empty)

    def test_bad_session(self, req):
        req.cookies = SimpleCookie()
        req.cookies["SESSID"] = "\0"

        with raises(SessionError):
            PoorSession(req)
