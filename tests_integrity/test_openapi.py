"""Tests for opanapi implementation"""
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
    url = environ.get("TEST_OPENAPI_URL", "").strip('/')
    if url:
        yield url
        return

    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/openapi3.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()
    process.wait()


@fixture
def session(url):
    session = Session()
    check_url(url+"/login", session=session, status_code=204)
    return session


class TestOpenAPI():
    """OpenAPI tests"""

    def test_plain_text(self, url):
        res = check_api(url+"/plain_text",
                        headers={'Accept': 'text/plain'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "text/plain"

    def test_content_header(self, url):
        res = check_api(url+"/response",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"

    def test_json_arg_integer(self, url):
        res = check_api(url+"/json/42",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '42'

    def test_json_arg_float(self, url):
        res = check_api(url+"/json/3.14",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '3.14'

    def test_json_arg_string(self, url):
        res = check_api(url+"/json/ok",
                        status_code=400,
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_json_post_unicode(self, url):
        data = "Česká Lípa"
        res = check_api(url+"/json", status_code=418,
                        method="POST", json=data,
                        response_spec=SPEC)
        assert res.json()["request"] == data
        assert False

    def test_json_post_unicode_struct(self, url):
        data = {"city": "Česká Lípa"}
        res = check_api(url+"/json", status_code=418,
                        method="PUT", json=data,
                        response_spec=SPEC)
        assert res.json()["request"] == data

    def test_invalid_post_data(self, url):
        check_api(url+"/json", status_code=400,
                  method="POST", data=b'\0',
                  headers={"Content-Type": "application/json"},
                  response_spec=SPEC)

    def test_arg_integer(self, url):
        res = check_api(url+"/arg/42",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == 42

    def test_arg_float(self, url):
        res = check_api(url+"/arg/3.14",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == 3.14

    def test_arg_uuid(self, url):
        res = check_api(url+"/arg/3e4666bf-d5e5-4aa7-b8ce-cefe41c7568a",
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == "3e4666bf-d5e5-4aa7-b8ce-cefe41c7568a"

    def test_arg_string(self, url):
        res = check_api(url+"/arg/ok",
                        status_code=400,
                        headers={'Accept': 'application/json'},
                        response_spec=SPEC)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_native_not_found(self, url):
        check_url(url+"/notexists_url", status_code=404)

    def test_native_method_not_allowed(self, url):
        check_url(url+"/plain_text", method="DELETE", status_code=405)

    def test_secrets_cookie(self, url, session):
        check_api(url+"/check/login", method="GET", session=session,
                  response_spec=SPEC)

    def test_secrets_api_key(self, url):
        check_api(url+"/check/api-key", method="GET",
                  headers={"API-Key": "xxx"},
                  response_spec=SPEC)

    def test_secrets_no_api_key(self, url):
        check_api(url+"/check/api-key", method="GET",
                  status_code=401,
                  response_spec=SPEC)
