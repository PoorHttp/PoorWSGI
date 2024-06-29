"""AESSession example integrity tests."""
from os import environ
from os.path import dirname, join, pardir

from pytest import fixture
from requests import Session

from .support import check_url, start_server

# pylint: disable=inconsistent-return-statements
# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name


@fixture(scope="module")
def url(request):
    """The URL (server fixture)."""
    val = environ.get("TEST_AES_SESSION_URL", "").strip('/')
    if val:
        return val

    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/aes_session.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()
    process.wait()


@fixture
def logged_in(url):
    """Fixture that logs in with valid credentials and returns the session."""
    session = Session()
    res = check_url(url + "/login", method="POST", session=session,
                    allow_redirects=False, status_code=302,
                    data={"username": "alice", "password": "secret"})
    assert "SESSID" in session.cookies
    cookie = res.headers["Set-Cookie"]
    assert "; HttpOnly" in cookie
    return session


class TestAESSession:
    """Tests for the AESSession example."""

    def test_root(self, url):
        check_url(url + "/")

    def test_login_get(self, url):
        check_url(url + "/login")

    def test_private_without_login_redirects(self, url):
        check_url(url + "/private", allow_redirects=False, status_code=302)

    def test_login_bad_password(self, url):
        check_url(url + "/login", method="POST", status_code=200,
                  data={"username": "alice", "password": "wrong"})

    def test_login_empty_username(self, url):
        check_url(url + "/login", method="POST", status_code=200,
                  data={"username": "", "password": "secret"})

    def test_login_sets_encrypted_cookie(self, url):
        session = Session()
        res = check_url(url + "/login", method="POST", session=session,
                        allow_redirects=False, status_code=302,
                        data={"username": "bob", "password": "secret"})
        assert "SESSID" in session.cookies
        cookie = res.headers["Set-Cookie"]
        assert "; HttpOnly" in cookie
        # Cookie value must not contain the username in plaintext
        assert "bob" not in session.cookies["SESSID"]

    def test_private_after_login(self, url, logged_in):
        res = check_url(url + "/private", session=logged_in)
        assert b"alice" in res.content

    def test_logout_clears_cookie(self, url, logged_in):
        res = check_url(url + "/logout", session=logged_in,
                        allow_redirects=False, status_code=302)
        assert "SESSID" not in logged_in.cookies
        cookie = res.headers["Set-Cookie"]
        assert "; HttpOnly" in cookie

    def test_private_after_logout_redirects(self, url, logged_in):
        check_url(url + "/logout", session=logged_in,
                  allow_redirects=False, status_code=302)
        check_url(url + "/private", session=logged_in,
                  allow_redirects=False, status_code=302)
