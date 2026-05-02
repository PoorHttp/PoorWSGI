"""Tests for OpenAPI implementation."""
from os import environ
from os.path import dirname, join, pardir

from pytest import fixture
from requests import Session

from . support import start_server, check_url, check_api
from . openapi import response_spec_json

SPEC = response_spec_json(
    join(dirname(__file__), pardir, "examples/openapi.json"))

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use


@fixture(scope="module")
def url(request):
    """Fixture for starting the OpenAPI example server."""
    process = None
    val = environ.get("TEST_OPENAPI_URL", "").rstrip('/')
    if val:
        yield val
    else:
        process = start_server(
            request,
            join(dirname(__file__), pardir, 'examples/openapi3.py'))
        yield "http://localhost:8080"  # server is running

    if process is not None:
        process.kill()
        process.wait()


@fixture
def session(url):
    """Fixture for creating a session and logging in."""
    session = Session()
    check_url(url+"/login", session=session, status_code=204)
    return session


class TestOpenAPI():
    """OpenAPI tests."""

    def test_plain_text(self, url):
        """Tests the /plain_text endpoint."""
        res = check_api(url+"/plain_text",
                        headers={'Accept': 'text/plain'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "text/plain"

    def test_content_header(self, url):
        """Tests the /response endpoint for Content-Type header."""
        res = check_api(url+"/response",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"

    def test_json_arg_integer(self, url):
        """Tests the /json/{arg} endpoint with an integer argument."""
        res = check_api(url+"/json/42",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '42'

    def test_json_arg_float(self, url):
        """Tests the /json/{arg} endpoint with a float argument."""
        res = check_api(url+"/json/3.14",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '3.14'

    def test_json_arg_string(self, url):
        """Tests the /json/{arg} endpoint with an invalid string argument."""
        res = check_api(url+"/json/ok",
                        status_code=400,
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_json_post_unicode(self, url):
        """Tests the /json POST endpoint with Unicode data."""
        data = "Česká Lípa"
        res = check_api(url+"/json", status_code=418,
                        method="POST", json=data,
                        response_spec=SPEC)
        assert res.json()["request"] == data

    def test_json_post_unicode_struct(self, url):
        """Tests the /json PUT endpoint with a Unicode struct."""
        data = {"city": "Česká Lípa"}
        res = check_api(url+"/json", status_code=418,
                        method="PUT", json=data,
                        response_spec=SPEC)
        assert res.json()["request"] == data

    def test_invalid_post_data(self, url):
        """Tests the /json POST endpoint with invalid data."""
        check_api(url+"/json", status_code=400,
                  method="POST", data=b'\0',
                  headers={"Content-Type": "application/json"},
                  response_spec=SPEC)

    def test_arg_integer(self, url):
        """Tests the /arg/{arg} endpoint with an integer argument."""
        res = check_api(url+"/arg/42",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == 42

    def test_arg_float(self, url):
        """Tests the /arg/{arg} endpoint with a float argument."""
        res = check_api(url+"/arg/3.14",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == 3.14

    def test_arg_uuid(self, url):
        """Tests the /arg/{arg} endpoint with a UUID argument."""
        res = check_api(url+"/arg/3e4666bf-d5e5-4aa7-b8ce-cefe41c7568a",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == "3e4666bf-d5e5-4aa7-b8ce-cefe41c7568a"

    def test_arg_string(self, url):
        """Tests the /arg/{arg} endpoint with an invalid string argument."""
        res = check_api(url+"/arg/ok",
                        status_code=400,
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_native_not_found(self, url):
        """Tests a native 404 Not Found response."""
        check_url(url+"/notexists_url", status_code=404)

    def test_native_method_not_allowed(self, url):
        """Tests a native 405 Method Not Allowed response."""
        check_url(url+"/plain_text", method="DELETE", status_code=405)

    def test_secrets_cookie(self, url, session):
        """Tests the /check/login endpoint with a valid session cookie."""
        check_api(url+"/check/login", method="GET", session=session,
                  response_spec=SPEC)

    def test_secrets_no_cookie(self, url):
        """Tests the /check/login endpoint without a session cookie, expecting
        401."""
        check_api(url+"/check/login", method="GET", status_code=401,
                  response_spec=SPEC)

    def test_secrets_api_key(self, url):
        """Tests the /check/api-key endpoint with a valid API key."""
        check_api(url+"/check/api-key", method="GET",
                  headers={"API-Key": "xxx"},
                  response_spec=SPEC)

    def test_secrets_no_api_key(self, url):
        """Tests the /check/api-key endpoint without an API key, expecting
        401."""
        check_api(url+"/check/api-key", method="GET",
                  status_code=401,
                  response_spec=SPEC)
