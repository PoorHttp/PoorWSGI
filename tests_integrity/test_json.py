"""Integrity tests for the JSON test/example application."""
from os import environ
from os.path import dirname, join, pardir
from time import time

from pytest import fixture

from . support import start_server, check_url

# pylint: disable=missing-function-docstring
# pylint: disable=inconsistent-return-statements
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use
# pylint: disable=consider-using-f-string


@fixture(scope="module")
def server(request):
    """Fixture for starting the JSON example server."""
    value = environ.get("TEST_SIMPLE_JSON_URL", "").strip('/')
    if value:
        return value

    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/simple_json.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()
    process.wait()


class TestHeaders:
    """Tests correct headers in the response."""

    def test_headers_empty(self, server):
        """Tests response headers for an empty request."""
        res = check_url(server+"/test/headers")
        assert "X-Powered-By" in res.headers
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data["XMLHttpRequest"] is False
        assert data["Accept-MimeType"]["html"] is False
        assert data["Accept-MimeType"]["xhtml"] is False
        assert data["Accept-MimeType"]["json"] is False

    def test_headers_ajax(self, server):
        """Tests response headers for an AJAX request."""
        res = check_url(
            server+"/test/headers",
            headers={'X-Requested-With': 'XMLHttpRequest',
                     'Accept': "text/html,text/xhtml,application/json"})
        assert "X-Powered-By" in res.headers
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data["XMLHttpRequest"] is True
        assert data["Accept-MimeType"]["html"] is True
        assert data["Accept-MimeType"]["xhtml"] is True
        assert data["Accept-MimeType"]["json"] is True


class TestRequest:
    """Tests various request attributes."""
    # pylint: disable=too-few-public-methods

    def test_timestamp(self, server):
        """Tests the timestamp attribute of the request."""
        now = time()
        res = check_url(server+"/timestamp")
        timestamp = res.json()["timestamp"]
        assert isinstance(timestamp, float)
        # uwsgi have more then 0.01, internal Python's server about 0.001
        assert abs(now - timestamp) < 0.1

    def test_json_request(self, server):
        """Tests handling of JSON requests."""
        data = [{"x": 124.2, "y": 100.1}]
        res = check_url(server+"/test/json", status_code=418,
                        method="POST", json=data, timeout=1)
        assert res.json() == {"message": "I'm teapot :-)",
                              "numbers": [0, 1, 2, 3, 4],
                              "request": data}

    def test_stream_request(self, server):
        """Tests handling of stream requests."""
        def generator():
            yield b'[{'
            for i in range(5):
                yield b'"%d": %d,' % (i, i)
            yield b'"end": null'
            yield b'}]'

        res = check_url(server+"/test/json", status_code=418,
                        method="POST", data=generator(),
                        headers={'Content-Type': 'application/json'})
        assert res.json() == {"message": "I'm teapot :-)",
                              "numbers": [0, 1, 2, 3, 4],
                              "request": [{"0": 0, "1": 1, "2": 2, "3": 3,
                                           "4": 4, "end": None}]}


class TestResponse:
    """Tests correct responses."""

    def test_json_response(self, server):
        """Tests a basic JSONResponse."""
        res = check_url(server+"/test/json", status_code=418, timeout=1)
        assert res.json() == {"message": "I'm teapot :-)",
                              "numbers": [0, 1, 2, 3, 4],
                              "request": {}}

    def test_json_generator_response(self, server):
        """Tests a JSONGeneratorResponse."""
        res = check_url(server+"/test/json-generator", status_code=418)
        assert res.json() == {"message": "I'm teapot :-)",
                              "numbers": [0, 1, 2, 3, 4],
                              "request": {}}

    def test_json_unicode(self, server):
        """Tests JSON response with Unicode characters."""
        data = "čeština"
        res = check_url(server+"/test/json", status_code=418,
                        method="POST", json=data)
        assert res.json()["request"] == data

    def test_json_unicode_struct(self, server):
        """Tests JSON response with a Unicode structure."""
        data = {"lang": "čeština"}
        res = check_url(server+"/test/json", status_code=418,
                        method="POST", json=data)
        assert res.json()["request"] == data

    def test_raw_unicode(self, server):
        """Tests raw Unicode in the response."""
        data = '{"name": "Ondřej Tůma"}'
        res = check_url(server+"/unicode")
        assert res.text == data
        assert int(res.headers['Content-Length']) == len(data.encode("utf-8"))

    def test_dict(self, server):
        """Tests returning a dictionary as a JSON response."""
        res = check_url(server+"/dict")
        assert res.json() == {"route": "/dict", "type": "dict"}

    def test_list(self, server):
        """Tests returning a list as a JSON response."""
        res = check_url(server+"/list")
        assert res.json() == [["key", "value"], ["route", "/list"],
                              ["type", "list"]]

    def test_bad_json_response(self, server):
        """Tests handling of a bad JSON response."""
        check_url(server+"/test/json", status_code=400,
                  method="POST", data=b"abraka crash",
                  headers={'Content-Type': 'application/json'})
