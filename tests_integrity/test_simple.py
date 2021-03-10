"""Base integrity test"""
from os import environ
from os.path import dirname, join, pardir
from time import time

from requests import Session
from pytest import fixture

from . support import start_server, check_url

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name


@fixture(scope="module")
def url(request):
    url = environ.get("TEST_SIMPLE_URL", "").strip('/')
    if url:
        return url

    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/simple.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()


@fixture
def session(url):
    session = Session()
    res = check_url(url+"/login", status_code=302, session=session,
                    allow_redirects=False)
    assert "SESSID" in session.cookies
    cookie = res.headers["Set-Cookie"]
    assert "; HttpOnly; " in cookie
    return session


class TestRequest():
    def test_timestamp(self, url):
        now = time()
        res = check_url(url+"/timestamp")
        timestamp = res.json()["timestamp"]
        assert isinstance(timestamp, float)
        # uwsgi have more then 0.01, internal Python's server about 0.001
        assert abs(now - timestamp) < 0.1


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
                              "numbers": [0, 1, 2, 3, 4],
                              "request": {}}

    def test_json_generator_response(self, url):
        res = check_url(url+"/test/json-generator", status_code=418)
        assert res.json() == {"message": "I\'m teapot :-)",
                              "numbers": [0, 1, 2, 3, 4],
                              "request": {}}

    def test_json_request(self, url):
        data = [{"x": 124.2, "y": 100.1}]
        res = check_url(url+"/test/json", status_code=418,
                        method="POST", json=data)
        assert res.json() == {"message": "I\'m teapot :-)",
                              "numbers": [0, 1, 2, 3, 4],
                              "request": data}

    def test_json_unicode(self, url):
        data = "čeština"
        res = check_url(url+"/test/json", status_code=418,
                        method="POST", json=data)
        assert res.json()["request"] == data

    def test_json_unicode_struct(self, url):
        data = {"lang": "čeština"}
        res = check_url(url+"/test/json", status_code=418,
                        method="POST", json=data)
        assert res.json()["request"] == data

    def test_empty_response(self, url):
        check_url("{url}/test/empty".format(url=url))


class TestSession():
    def test_login(self, url):
        check_url(url+"/login", status_code=302, allow_redirects=False)

    def test_logout(self, url, session):
        res = check_url(url+"/logout", session=session,
                        allow_redirects=False, status_code=302)
        assert "SESSID" not in session.cookies      # cookie is expired
        cookie = res.headers["Set-Cookie"]          # header must exists
        assert "; HttpOnly; " in cookie

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

    def test_none_error(self, url):
        """Test debug output - which handler crash on none result."""
        res = check_url(url+"/none-error", status_code=500)
        assert "none_error_handler" in res.text

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
