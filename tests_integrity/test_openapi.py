from os import environ

from . support import check_url

URL = environ.get("TEST_OPENAPI_URL", "http://localhost:8080").strip('/')


class TestOpenAPI():
    def test_plain_text(self):
        res = check_url(URL+"/plain_text")
        assert res.headers["Content-Type"] == "text/plain"

    def test_json_arg_integer(self):
        res = check_url(URL+"/json/42")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '42'

    def test_json_arg_float(self):
        res = check_url(URL+"/json/3.14")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '3.14'

    def test_json_arg_string(self):
        res = check_url(URL+"/json/ok", status_code=400)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_arg_integer(self):
        res = check_url(URL+"/arg/42")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("integer_arg") == 42

    def test_arg_float(self):
        res = check_url(URL+"/arg/3.14")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("float_arg") == 3.14

    def test_arg_string(self):
        res = check_url(URL+"/arg/ok", status_code=404)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None
