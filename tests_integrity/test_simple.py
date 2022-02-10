"""Base integrity test"""
from os import environ
from os.path import dirname, join, pardir

from requests import Session
from pytest import fixture

from . support import start_server, check_url

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name
# pylint: disable=consider-using-f-string


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


class TestRequest:
    """Test for requests."""
    # pylint: disable=too-few-public-methods
    def test_stream_request(self, url):
        def generator():
            for i in range(5):
                yield b'%i' % i

        check_url(url+"/yield", method="POST", data=generator())


class TestResponses():
    """Tests for Responses"""
    def test_yield(self, url):
        """yield function is done by GeneratorResponse."""
        check_url(url+"/yield")

    def test_file_obj_response(self, url):
        res = check_url(url+"/simple")
        assert 'Content-Length' in res.headers
        assert 'StorageFactory' in res.text
        assert '@app.route' in res.text
        assert '@app.before_response' in res.text

    def test_file_response(self, url):
        res = check_url(url+"/simple.py")
        assert 'Content-Length' in res.headers
        assert 'StorageFactory' in res.text
        assert '@app.route' in res.text
        assert '@app.before_response' in res.text

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

    def test_form_upload_small(self, url, session):
        manifest = join(dirname(__file__), pardir, 'MANIFEST.in')
        files = {'file_0': ('MANIFEST.in', open(manifest, 'rb'),
                            'text/plain', {'Expires': '0'})}
        res = check_url(url+"/test/upload", method="POST", session=session,
                        allow_redirects=False, files=files)
        assert 'MANIFEST.in' in res.text
        assert 'graft' in res.text
        assert 'global-exclude' in res.text


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
