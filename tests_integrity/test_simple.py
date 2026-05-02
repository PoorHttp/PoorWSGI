"""Base integrity tests."""
from os import environ
from os.path import dirname, join, pardir

from pytest import fixture

from .support import check_url, start_server

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name
# pylint: disable=consider-using-f-string
# pylint: disable=duplicate-code


@fixture(scope="module")
def url(request):
    """The URL (server fixture)."""
    process = None
    val = environ.get("TEST_SIMPLE_URL", "").rstrip('/')
    if val:
        yield val
    else:
        process = start_server(
            request,
            join(dirname(__file__), pardir, 'examples/simple.py'))
        yield "http://localhost:8080"  # server is running

    if process is not None:
        process.kill()
        process.wait()


class TestSimple():
    """Tests for routes."""

    def test_root(self, url):
        """Tests the root endpoint."""
        check_url(url)

    def test_static(self, url):
        """Tests the /test/static endpoint."""
        check_url(url+"/test/static")

    def test_static_not_modified(self, url):
        """Tests the /test/static endpoint with If-None-Match header for Not
        Modified."""
        res = check_url(url+"/test/static")
        check_url(url+"/test/static", status_code=304,
                  headers={'ETag': res.headers.get('ETag')})

    def test_exception_not_modified(self, url):
        """Tests the /not-modified endpoint for Not Modified."""
        check_url(url+"/not-modified", status_code=304)

    def test_variable_int(self, url):
        """Tests a route with an integer variable."""
        check_url(url+"/test/123")

    def test_variable_float(self, url):
        """Tests a route with a float variable."""
        check_url(url+"/test/123.679")

    def test_variable_user(self, url):
        """Tests a route with a user (email) variable."""
        check_url(url+"/test/teste@tester.net")

    def test_variable_uuid(self, url):
        """Tests a route with a UUID variable."""
        check_url(url+"/test/123e4567-e89b-12d3-a456-426655440000")

    def test_variable_uuid_upper(self, url):
        """Tests a route with an uppercase UUID variable."""
        check_url(url+"/test/123E4567-E89B-12D3-A456-426655440000")

    def test_debug_info(self, url):
        """Tests the /debug-info endpoint."""
        check_url(url+"/debug-info")


class TestRequest:
    """Tests for requests."""
    # pylint: disable=too-few-public-methods

    def test_stream_request(self, url):
        """Tests stream requests."""
        def generator():
            for i in range(5):
                yield b'%i' % i

        check_url(url+"/yield", method="POST", data=generator())


class TestResponses():
    """Tests for Responses."""

    def test_yield(self, url):
        """Tests the yield function with GeneratorResponse."""
        check_url(url+"/yield")

    def test_file_obj_response(self, url):
        """Tests FileObjResponse."""
        res = check_url(url+"/simple")
        assert 'Content-Length' in res.headers
        assert 'StorageFactory' in res.text
        assert '@app.route' in res.text
        assert '@app.before_response' in res.text

    def test_file_response(self, url):
        """Tests FileResponse."""
        res = check_url(url+"/simple.py")
        assert 'Content-Length' in res.headers
        assert 'StorageFactory' in res.text
        assert '@app.route' in res.text
        assert '@app.before_response' in res.text

    def test_file_response_304_last_modified(self, url):
        """Tests FileResponse with If-Modified-Since header for 304 Not
        Modified."""
        res = check_url(url+"/simple.py")
        last_modified = res.headers.get('Last-Modified')
        check_url(url+"/simple.py",
                  headers={'If-Modified-Since': last_modified},
                  status_code=304)

    def test_file_response_304_etag(self, url):
        """Tests FileResponse with ETag header for 304 Not Modified."""
        res = check_url(url+"/simple.py")
        etag = res.headers.get('ETag')
        check_url(url+"/simple.py",
                  headers={'If-None-Match': etag},
                  status_code=304)

    def test_none_no_content(self, url):
        """Tests None response resulting in 204 No Content."""
        check_url(url+"/none", status_code=204)


class TestPartialResponse():
    """Tests for Partial Responses."""

    def test_file(self, url):
        """Tests partial file response."""
        res = check_url(url+"/simple.py",
                        headers={'Range': 'bytes=-100'},
                        status_code=206)
        assert len(res.text) == 100
        assert res.text[-22:] == "httpd.serve_forever()\n"

    def test_empty_response(self, url):
        """Tests the /test/empty endpoint for 204 No Content."""
        check_url("{url}/test/empty".format(url=url), status_code=204)

    def test_empty(self, url):
        """Tests the /test/partial/empty endpoint with no range."""
        check_url("{url}/test/partial/empty".format(url=url), status_code=200)

    def test_empty_first_100(self, url):
        """Tests the /test/partial/empty endpoint with a bytes range, expecting
        416."""
        check_url("{url}/test/partial/empty".format(url=url),
                  headers={'Range': 'bytes=0-99'},
                  status_code=416)

    def test_first_15(self, url):
        """Tests a partial generator response for the first 15 bytes."""
        res = check_url("{url}/test/partial/generator".format(url=url),
                        headers={'Range': 'bytes=0-14'},
                        status_code=206)
        assert len(res.text) == 15
        assert res.text[-22:] == "line 0\nline 1\nl"

    def test_last_15(self, url):
        """Tests a partial generator response for the last 15 bytes."""
        res = check_url("{url}/test/partial/generator".format(url=url),
                        headers={'Range': 'bytes=-15'},
                        status_code=206)
        assert len(res.text) == 15
        assert res.text[-22:] == "\nline 8\nline 9\n"

    def test_unicodes(self, url):
        """Tests a partial response with Unicode range units."""
        res = check_url("{url}/test/partial/unicodes".format(url=url),
                        headers={'Range': 'unicodes=50-99'},
                        status_code=206)
        assert len(res.text) == 50
        assert len(res.text) < len(res.text.encode("utf-8"))

    def test_form_get(self, url):
        """Tests GET form access."""
        check_url(url+"/test/form")

    def test_form_post(self, url):
        """Tests POST form submission."""
        check_url(url+"/test/form", method="POST")

    def test_form_upload(self, url):
        """Tests file upload via form."""
        with open(__file__, 'rb') as _file:
            files = {'file_0': ('testfile.py', _file,
                                'text/x-python', {'Expires': '0'})}
            res = check_url(url+"/test/upload", method="POST",
                            allow_redirects=False, files=files)
            assert 'testfile.py' in res.text
            assert __doc__ in res.text
            assert 'anything' in res.text

    def test_form_upload_small(self, url):
        """Tests small file upload via form."""
        manifest = join(dirname(__file__), pardir, 'MANIFEST.in')
        with open(manifest, 'rb') as _file:
            files = {'file_0': ('MANIFEST.in', _file,
                                'text/plain', {'Expires': '0'})}
            res = check_url(url+"/test/upload", method="POST",
                            allow_redirects=False, files=files)
            assert 'MANIFEST.in' in res.text
            assert 'graft' in res.text
            assert 'global-exclude' in res.text


class TestErrors():
    """Integrity tests for native HTTP state handlers."""

    def test_internal_server_error(self, url):
        """Tests the /internal-server-error endpoint."""
        check_url(url+"/internal-server-error", status_code=500)

    def test_bad_request(self, url):
        """Tests the /bad-request endpoint."""
        check_url(url+"/bad-request", status_code=400)

    def test_forbidden(self, url):
        """Tests the /forbidden endpoint."""
        check_url(url+"/forbidden", status_code=403)

    def test_not_found(self, url):
        """Tests the /no-page endpoint for 404 Not Found."""
        check_url(url+"/no-page", status_code=404)

    def test_method_not_allowed(self, url):
        """Tests the /internal-server-error endpoint with an disallowed
        method."""
        check_url(url+"/internal-server-error", method="PUT", status_code=405)

    def test_not_implemented(self, url):
        """Tests the /not-implemented endpoint."""
        check_url(url+"/not-implemented", status_code=501)
