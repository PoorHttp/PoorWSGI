from os import urandom
from http.cookies import SimpleCookie

from pytest import fixture

from poorwsgi.session import PoorSession


class Request:
    secret_key = urandom(32)
    cookies = SimpleCookie()


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
