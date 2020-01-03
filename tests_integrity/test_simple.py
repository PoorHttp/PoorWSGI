"""Base integrity test"""
from os import environ
from os.path import dirname, join, pardir
from sys import executable
from subprocess import Popen
from time import sleep
from socket import socket, error as SocketError

from requests import Session
from pytest import fixture

from . support import check_url

URL = environ.get("TEST_SIMPLE_URL", "").strip('/')
PROCESS = None


def setUpModule():
    global PROCESS
    global URL

    if not URL:
        URL = "http://localhost:8080"
        print("Starting wsgi application...")
        PROCESS = Popen([executable,
                         join(dirname(__file__), pardir,
                              "examples/simple.py")])
        assert PROCESS is not None
        for i in range(20):
            sck = socket()
            try:
                sck.connect(("localhost", 8080))
                return
            except SocketError:
                sleep(0.1)
            finally:
                sck.close()
        raise RuntimeError("Server not started in 2 seconds")


def tearDownModule():
    PROCESS.kill()


@fixture
def session():
    session = Session()
    check_url(URL+"/login", status_code=302, session=session,
              allow_redirects=False)
    assert "SESSID" in session.cookies
    return session


class TestSimple():
    def test_root(self):
        check_url(URL)

    def test_static(self):
        check_url(URL+"/test/static")

    def test_variable_int(self):
        check_url(URL+"/test/123")

    def test_variable_float(self):
        check_url(URL+"/test/123.679")

    def test_variable_user(self):
        check_url(URL+"/test/teste@tester.net")

    def test_debug_info(self):
        check_url(URL+"/debug-info")

    def test_404(self):
        check_url(URL+"/no-page", status_code=404)

    def test_500(self):
        check_url(URL+"/internal-server-error", status_code=500)

    def test_headers_empty(self):
        res = check_url(URL+"/test/headers")
        assert "X-Powered-By" in res.headers
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data["XMLHttpRequest"] is False
        assert data["Accept-MimeType"]["html"] is False
        assert data["Accept-MimeType"]["xhtml"] is False
        assert data["Accept-MimeType"]["json"] is False

    def test_headers_ajax(self):
        res = check_url(
            URL+"/test/headers",
            headers={'X-Requested-With': 'XMLHttpRequest',
                     'Accept': "text/html,text/xhtml,application/json"})
        assert "X-Powered-By" in res.headers
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data["XMLHttpRequest"] is True
        assert data["Accept-MimeType"]["html"] is True
        assert data["Accept-MimeType"]["xhtml"] is True
        assert data["Accept-MimeType"]["json"] is True

    def test_yield(self):
        check_url(URL+"/yield")


class TestSession():
    def test_login(self):
        check_url(URL+"/login", status_code=302, allow_redirects=False)

    def test_logout(self, session):
        check_url(URL+"/logout", session=session)
        assert "SESSID" not in session.cookies

    def test_form_get_not_logged(self):
        check_url(URL+"/test/form", status_code=302, allow_redirects=False)

    def test_form_get_logged(self, session):
        check_url(URL+"/test/form", session=session, allow_redirects=False)

    def test_form_post(self, session):
        check_url(URL+"/test/form", method="POST", session=session,
                  allow_redirects=False)

    def test_form_upload(self, session):
        files = {'file_0': ('testfile.py', open(__file__, 'rb'),
                            'text/x-python', {'Expires': '0'})}
        res = check_url(URL+"/test/upload", method="POST", session=session,
                        allow_redirects=False, files=files)
        assert 'testfile.py' in res.text
        assert __doc__ in res.text
        assert 'anything' in res.text
