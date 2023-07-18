"""Test for request module fuctionality."""
from io import BytesIO
from time import time
from typing import Dict, Any

from pytest import fixture, raises

from poorwsgi import Application
from poorwsgi.request import JsonDict, JsonList, parse_json_request, \
    EmptyForm, Args, FieldStorage, Request
from poorwsgi.response import HTTPException

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name
# pylint: disable=too-few-public-methods


@fixture(scope='session')
def app():
    return Application(__name__)


class TestEmpty:
    """Test for Empty class"""
    def test_emptry_form(self):
        form = EmptyForm()
        assert form.getvalue("name") is None
        assert form.getvalue("name", "PooWSGI") == "PooWSGI"
        assert form.getfirst("name") is None
        assert form.getfirst("age", "23", int) == 23
        assert tuple(form.getlist("values", ("3", "4"), int)) == (3, 4)
        assert not tuple(form.getlist("values"))


class TestJSON:
    """Test for JSON input class"""
    def test_json_dict(self):
        json = JsonDict(age=23, items=[1, 2], size="25")
        assert json.getvalue("no") is None
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age") == 23
        assert json.getfirst("no") is None
        assert json.getfirst("age") == "23"
        assert json.getfirst("items") == "1"
        assert tuple(json.getlist("items", fce=str)) == ("1", "2")
        assert tuple(json.getlist("values", ("3", "4"), int)) == (3, 4)
        assert not tuple(json.getlist("values"))

    def test_json_list_empty(self):
        json = JsonList()
        assert json.getvalue("no") is None
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age", 23) == 23
        assert json.getfirst("no") is None
        assert json.getfirst("age", 23) == "23"
        assert json.getfirst("name", "2", int) == 2
        assert tuple(json.getlist("ages", ["1", "2"], int)) == (1, 2)
        assert not tuple(json.getlist("ages"))

    def test_json_list(self):
        json = JsonList([1, 2])
        assert json.getvalue("age") == 1
        assert json.getfirst("age") == "1"
        assert tuple(json.getlist("items", fce=str)) == ("1", "2")


class TestArgs:
    """Tests for Args class"""
    class Req:
        """Request class mock"""
        app = None
        query = ''
        environ: Dict[str, Any] = {}

    def test_empty(self):
        args = Args(self.Req())
        assert args.getvalue("no") is None
        assert args.getvalue("name", "PooWSGI") == "PooWSGI"
        assert args.getfirst("no") is None
        assert args.getfirst("age", "23", int) == 23
        assert tuple(args.getlist("values", ("3", "4"), int)) == (3, 4)
        assert not tuple(args.getlist("values"))
        assert args.get("no") is None


class TestForm:
    """Tests for FieldStorage"""
    class Req:
        """Request class mock"""
        environ: Dict[str, Any] = {}

    def test_empty(self):
        form = FieldStorage(self.Req())
        assert form.getvalue("no") is None
        assert form.getvalue("name", "PooWSGI") == "PooWSGI"
        assert form.getfirst("no") is None
        assert form.getfirst("age", "23", int) == 23
        assert tuple(form.getlist("values", ("3", "4"), int)) == (3, 4)
        assert not tuple(form.getlist("values"))


class TestParseJson:
    """Tests for parsing JSON requests."""
    def test_str(self):
        assert isinstance(parse_json_request(b"{}"), JsonDict)

    def test_list(self):
        assert isinstance(parse_json_request(b"[]"), JsonList)

    def test_text(self):
        assert isinstance(parse_json_request(b'"text"'), str)

    def test_int(self):
        assert isinstance(parse_json_request(b"23"), int)

    def test_float(self):
        assert isinstance(parse_json_request(b"3.14"), float)

    def test_bool(self):
        assert isinstance(parse_json_request(b"true"), bool)

    def test_null(self):
        assert parse_json_request(b"null") is None

    def test_error(self):
        with raises(HTTPException) as err:
            parse_json_request(BytesIO(b"abraka"))
        assert err.value.args[0] == 400
        assert 'error' in err.value.args[1]

    def test_unicode(self):
        rval = parse_json_request(b'"\\u010de\\u0161tina"')
        assert rval == "čeština"

    def test_utf8(self):
        rval = parse_json_request(b'"\xc4\x8de\xc5\xa1tina"')
        assert rval == "čeština"

    def test_unicode_struct(self):
        rval = parse_json_request(b'{"lang":"\\u010de\\u0161tina"}')
        assert rval == {"lang": "čeština"}

    def test_utf_struct(self):
        rval = parse_json_request(b'{"lang":"\xc4\x8de\xc5\xa1tina"}')
        assert rval == {"lang": "čeština"}


class TestRequest:
    """Test Request class."""
    def test_host_wsgi(self, app):
        env = {
             'PATH_INFO': '/path',
             'wsgi.url_scheme': 'http',
             'SERVER_NAME': 'example.org',
             'SERVER_PORT': '80',
             'REQUEST_STARTTIME': time()
        }
        req = Request(env, app)
        assert req.server_scheme == 'http'
        assert req.hostname == 'example.org'
        assert req.host_port == 80
        assert req.construct_url('/x') == 'http://example.org/x'

    def test_host_header(self, app):
        env = {
             'PATH_INFO': '/path',
             'wsgi.url_scheme': 'http',
             'SERVER_NAME': 'example.org',
             'SERVER_PORT': '80',
             'REQUEST_STARTTIME': time(),
             'HTTP_HOST': 'example.net:8080'
        }
        req = Request(env, app)
        assert req.server_scheme == 'http'
        assert req.hostname == 'example.net'
        assert req.host_port == 8080
        assert req.construct_url('/x') == 'http://example.net:8080/x'

    def test_forward_header(self, app):
        env = {
             'PATH_INFO': '/path',
             'wsgi.url_scheme': 'http',
             'SERVER_NAME': 'example.org',
             'SERVER_PORT': '80',
             'REQUEST_STARTTIME': time(),
             'HTTP_HOST': 'example.net:8080',
             'HTTP_X_FORWARDED_PROTO': 'https',
             'HTTP_X_FORWARDED_HOST': 'example.com'
        }
        req = Request(env, app)
        assert req.server_scheme == 'http'
        assert req.hostname == 'example.net'
        assert req.host_port == 8080
        assert req.construct_url('/x') == 'https://example.com/x'

    def test_empty_form(self, app):
        env = {
            'PATH_INFO': '/path',
            'SERVER_PROTOCOL': 'HTTP/1.0',
            'REQUEST_METHOD': 'POST',
            'REQUEST_STARTTIME': time(),
            'HTTP_CONTENT_TYPE': 'multipart/form-data',
            'wsgi.input': BytesIO()
            }
        req = Request(env, app)
        assert app.auto_form is True
        assert req.is_body_request is False
        assert req.mime_type in app.form_mime_types
        assert isinstance(req.form, EmptyForm)
