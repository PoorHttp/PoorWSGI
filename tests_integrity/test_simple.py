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


@fixture(scope="module")
def url(request):
    url = environ.get("TEST_SIMPLE_URL", "").strip('/')
    if url:
        return url

    process = None
    print("Starting wsgi application...")
    if request.config.getoption("--with-uwsgi"):
        process = Popen(["uwsgi", "--plugin", "python3",
                         "--http-socket", "localhost:8080", "--wsgi-file",
                         join(dirname(__file__), pardir,
                              "examples/simple.py")])
    else:
        process = Popen([executable,
                         join(dirname(__file__), pardir,
                              "examples/simple.py")])
    assert process is not None
    connect = False
    for i in range(20):
        sck = socket()
        try:
            sck.connect(("localhost", 8080))
            connect = True
            break
        except SocketError:
            sleep(0.1)
        finally:
            sck.close()
    if not connect:
        process.kill()
        raise RuntimeError("Server not started in 2 seconds")

    yield "http://localhost:8080"  # server is running
    process.kill()


@fixture
def session(url):
    session = Session()
    check_url(url+"/login", status_code=302, session=session,
              allow_redirects=False)
    assert "SESSID" in session.cookies
    return session


class TestSimple():
    def test_root(self, url):
        check_url(url)

    def test_static(self, url):
        check_url(url+"/test/static")

    def test_variable_int(self, url):
        check_url(url+"/test/123")

    def test_variable_float(self, url):
        check_url(url+"/test/123.679")

    def test_variable_user(self, url):
        check_url(url+"/test/teste@tester.net")

    def test_debug_info(self, url):
        check_url(url+"/debug-info")

    def test_headers_empty(self, url):
        res = check_url(url+"/test/headers")
        assert "X-Powered-By" in res.headers
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data["XMLHttpRequest"] is False
        assert data["Accept-MimeType"]["html"] is False
        assert data["Accept-MimeType"]["xhtml"] is False
        assert data["Accept-MimeType"]["json"] is False

    def test_headers_ajax(self, url):
        res = check_url(
            url+"/test/headers",
            headers={'X-Requested-With': 'XMLHttpRequest',
                     'Accept': "text/html,text/xhtml,application/json"})
        assert "X-Powered-By" in res.headers
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data["XMLHttpRequest"] is True
        assert data["Accept-MimeType"]["html"] is True
        assert data["Accept-MimeType"]["xhtml"] is True
        assert data["Accept-MimeType"]["json"] is True


class TestResponses():
    def test_yield(self, url):
        """yield function is done by GeneratorResponse."""
        check_url(url+"/yield")

    def test_file_response(self, url):
        res = check_url(url+"/simple.py")
        assert 'StorageFactory' in res.text
        assert '@app.route' in res.text
        assert '@app.before_request' in res.text

    def test_json_response(self, url):
        res = check_url(url+"/test/json", status_code=418)
        assert res.json() == {"message": "I\'m teapot :-)",
                              "numbers": [0, 1, 2, 3, 4]}

    def test_empty_response(self, url):
        check_url(f"{url}/test/empty")


class TestSession():
    def test_login(self, url):
        check_url(url+"/login", status_code=302, allow_redirects=False)

    def test_logout(self, url, session):
        check_url(url+"/logout", session=session)
        assert "SESSID" not in session.cookies

    def test_form_get_not_logged(self, url):
        check_url(url+"/test/form", status_code=302, allow_redirects=False)

    def test_form_get_logged(self, url, session):
        check_url(url+"/test/form", session=session, allow_redirects=False)

    def test_form_post(self, url, session):
        check_url(url+"/test/form", method="POST", session=session,
                  allow_redirects=False)

    def test_form_upload(self, url, session):
        files = {'file_0': ('testfile.py', open(__file__, 'rb'),
                            'text/x-python', {'Expires': '0'})}
        res = check_url(url+"/test/upload", method="POST", session=session,
                        allow_redirects=False, files=files)
        assert 'testfile.py' in res.text
        assert __doc__ in res.text
        assert 'anything' in res.text


class TestErrors():
    """Integrity tests for native http state handlers."""
    def test_internal_server_error(self, url):
        check_url(url+"/internal-server-error", status_code=500)

    def test_bad_request(self, url):
        check_url(url+"/bad-request", status_code=400)

    def test_forbidden(self, url):
        check_url(url+"/forbidden", status_code=403)

    def test_not_found(self, url):
        check_url(url+"/no-page", status_code=404)

    def test_method_not_allowed(self, url):
        check_url(url+"/internal-server-error", method="PUT", status_code=405)

    def test_not_implemented(self, url):
        check_url(url+"/not-implemented", status_code=501)
