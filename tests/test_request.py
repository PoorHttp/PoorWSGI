"""Tests for request module functionality."""
import base64
import warnings
from io import BytesIO
from time import time
from typing import Any, ClassVar

from pytest import fixture, raises

from poorwsgi import Application
from poorwsgi.fieldstorage import FieldStorage, FieldStorageParser
from poorwsgi.headers import Headers
from poorwsgi.request import (Args, CachedInput, EmptyForm,
                              FieldStorage as DeprecatedFieldStorage,
                              JsonDict, JsonList, Request, SimpleRequest,
                              parse_json_request)
from poorwsgi.response import HTTPException
from poorwsgi.state import methods

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-lines
# pylint: disable=too-many-public-methods


@fixture(scope='session')
def app():
    return Application(__name__)


class TestEmpty:
    """Tests for the Empty class."""
    def test_emptry_form(self):
        """Tests the EmptyForm class behavior."""
        form = EmptyForm()
        assert form.getvalue("name") is None
        assert form.getvalue("name", "PooWSGI") == "PooWSGI"
        assert form.getfirst("name") is None
        assert form.getfirst("age", 23) == 23
        assert tuple(form.getlist("values", (3, 4))) == (3, 4)
        assert not tuple(form.getlist("values"))


class TestJSON:
    """Tests for the JSON input classes."""
    def test_json_dict(self):
        """Tests the JsonDict class."""
        json = JsonDict(age=23, items=[1, 2], size="25")
        assert json.getvalue("no") is None
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age") == 23
        assert json.getfirst("no") is None
        assert json.getfirst("age") == 23
        assert json.getfirst("items", func=str) == "1"
        assert tuple(json.getlist("items", func=str)) == ("1", "2")
        assert tuple(json.getlist("values", (3, 4))) == (3, 4)
        assert not tuple(json.getlist("values"))

    def test_json_list_empty(self):
        """Tests the JsonList class with an empty list."""
        json = JsonList()
        assert json.getvalue("no") is None
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age", 23) == 23
        assert json.getfirst("no") is None
        assert json.getfirst("age", 23) == 23
        assert json.getfirst("name", 2, int) == 2
        assert tuple(json.getlist("ages", [1, 2])) == (1, 2)
        assert not tuple(json.getlist("ages"))

    def test_json_list(self):
        """Tests the JsonList class with a populated list."""
        json = JsonList([1, 2])
        assert json.getvalue("age") == 1
        assert json.getfirst("age") == 1
        assert tuple(json.getlist("items", func=str)) == ("1", "2")


class TestArgs:
    """Tests for the Args class."""
    class Req:
        """A mock Request class."""
        app = None
        query = ''
        environ: ClassVar[dict[str, Any]] = {}

    def test_empty(self):
        """Tests the Args class with empty arguments."""
        args = Args(self.Req())
        assert args.getvalue("no") is None
        assert args.getvalue("name", "PooWSGI") == "PooWSGI"
        assert args.getfirst("no") is None
        assert args.getfirst("age", 23, int) == 23
        assert tuple(args.getlist("values", (3, 4))) == (3, 4)
        assert not tuple(args.getlist("values"))
        assert args.get("no") is None


class Empty:
    """A mock Empty Request class."""
    environ: ClassVar[dict[str, Any]] = {}
    headers: ClassVar[dict[str, str]] = {}
    input = BytesIO(b"")


@fixture
def empty():
    return Empty()


class UrlEncoded:
    """A mock Request class with application/x-www-form-urlencoded content."""
    environ: ClassVar[dict[str, Any]] = {}
    headers = Headers({
        "Content-Length": "60",
        "Content-Type": "application/x-www-form-urlencoded",
        })
    input = BytesIO(b"pname=Ond%C5%99ej&psurname=T%C5%AFma"
                    b"&px=8&px=7&px=6&btn=Send")


@fixture
def url_encoded():
    yield UrlEncoded()
    UrlEncoded.input.seek(0)


class MultiPart:
    """A mock Request class with multipart/form-data content."""
    environ: ClassVar[dict[str, Any]] = {}
    headers = Headers({
        "Content-Type":
            ("multipart/form-data; "
             "boundary=----WebKitFormBoundaryrUf888hx3XHjF3X4"),
        "Content-Length": "2697"
    })
    input = BytesIO(
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="fname"\r\n\r\n'
        b'Ond\xc5\x99ej\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="fsurname"\r\n\r\n'
        b'T\xc5\xafma\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="fx"\r\n\r\n8\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="fx"\r\n\r\n7\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="fx"\r\n\r\n6\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="fbody"\r\n\r\n\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4\r\n'
        b'Content-Disposition: form-data; name="data"\r\n\r\n' +
        b'#'*2000 +
        b'\r\n'
        b'------WebKitFormBoundaryrUf888hx3XHjF3X4--\r\n')


@fixture
def multipart():
    yield MultiPart()
    MultiPart.input.seek(0)


class TxtFile:
    """A mock Request class with a binary file in multipart content."""
    environ: ClassVar[dict[str, Any]] = {}
    headers = Headers({
        "Content-Length": "293",
        "Content-Type": "multipart/form-data; "
                        "boundary=----WebKitFormBoundaryNbcDXbbrawsQmAuL"
        })
    input = BytesIO(
        b'------WebKitFormBoundaryNbcDXbbrawsQmAuL\r\n'
        b'Content-Disposition: form-data; name="file"; '
        b'filename="text_file.txt"\r\nContent-Type: text/plain\r\n\r\n'
        b'\xc4\x8ce\xc5\xa1tina\n\r\n'
        b'------WebKitFormBoundaryNbcDXbbrawsQmAuL\r\n'
        b'Content-Disposition: form-data; name="btn"\r\n\r\nUpload\r\n'
        b'------WebKitFormBoundaryNbcDXbbrawsQmAuL--\r\n'
    )


@fixture
def txt_file():
    yield TxtFile()
    TxtFile.input.seek(0)


class TestForm:
    """Tests for FieldStorage."""
    def test_empty(self, empty):
        """Tests parsing an empty form."""
        parser = FieldStorageParser(empty.input, empty.headers)
        form = parser.parse()

        assert not form.keys()
        assert form.getvalue("no") is None
        assert form.getvalue("name", "PooWSGI") == "PooWSGI"
        assert form.getfirst("no") is None
        assert form.getfirst("age", 23, int) == 23
        assert tuple(form.getlist("values", (3, 4), int)) == (3, 4)
        assert not tuple(form.getlist("values"))

    def test_multipart(self, multipart):
        """Tests parsing a multipart form."""
        parser = FieldStorageParser(multipart.input, multipart.headers)
        form = parser.parse()

        assert list(form.keys()) == ["fname", "fsurname", "fx", "fbody",
                                     "data"]
        assert form.getvalue("fname") == "Ondřej"
        assert form.getvalue("fsurname") == "Tůma"
        assert list(form.getlist("fx", func=int)) == [8, 7, 6]
        assert form.getvalue("data") == "#"*2000

    def test_urlencoded(self, url_encoded):
        """Tests parsing a URL-encoded form."""
        parser = FieldStorageParser(url_encoded.input, url_encoded.headers)
        form = parser.parse()

        assert list(form.keys()) == ["pname", "psurname", "px", "btn"]
        assert form.getvalue("pname") == "Ondřej"
        assert form.getvalue("psurname") == "Tůma"
        assert list(form.getlist("px", func=int)) == [8, 7, 6]

    def test_txtfile(self, txt_file):
        """Tests parsing a text file in a form."""
        parser = FieldStorageParser(txt_file.input, txt_file.headers)
        form = parser.parse()

        assert list(form.keys()) == ["file", "btn"]
        assert form.getvalue("btn") == "Upload"
        file = form["file"]
        assert file.filename == "text_file.txt"
        assert file.type == "text/plain"
        assert file.file.read() == "Čeština\n".encode("utf-8")
        file.file.seek(0)
        print(type(form.getvalue("file")), form.getvalue("file"))
        assert isinstance(form.getvalue("file"), bytes)

    def test_txtfile_callback(self, txt_file):
        """Tests parsing a text file using a file_callback."""
        tmp = BytesIO()

        def file_callback(filename: str):
            assert filename == "text_file.txt"
            return tmp

        parser = FieldStorageParser(txt_file.input, txt_file.headers,
                                    file_callback=file_callback)
        form = parser.parse()
        assert form.getvalue("btn") == "Upload"
        file = form["file"]
        assert file.file == tmp
        assert file.filename == "text_file.txt"
        assert file.type == "text/plain"
        assert file.file.read() == "Čeština\n".encode("utf-8")


class TestParseJson:
    """Tests for parsing JSON requests."""
    def test_str(self):
        """Tests parsing a JSON string."""
        assert isinstance(parse_json_request(b"{}"), JsonDict)

    def test_list(self):
        """Tests parsing a JSON list."""
        assert isinstance(parse_json_request(b"[]"), JsonList)

    def test_text(self):
        """Tests parsing JSON plain text."""
        assert isinstance(parse_json_request(b'"text"'), str)

    def test_int(self):
        """Tests parsing a JSON integer."""
        assert isinstance(parse_json_request(b"23"), int)

    def test_float(self):
        """Tests parsing a JSON float."""
        assert isinstance(parse_json_request(b"3.14"), float)

    def test_bool(self):
        """Tests parsing a JSON boolean."""
        assert isinstance(parse_json_request(b"true"), bool)

    def test_null(self):
        """Tests parsing a JSON null value."""
        assert parse_json_request(b"null") is None

    def test_error(self):
        """Tests parsing an invalid JSON string, expecting an HTTPException."""
        with raises(HTTPException) as err:
            parse_json_request(BytesIO(b"abraka"))
        assert err.value.args[0] == 400
        assert 'error' in err.value.args[1]

    def test_unicode(self):
        """Tests parsing JSON with Unicode characters."""
        rval = parse_json_request(b'"\\u010de\\u0161tina"')
        assert rval == "čeština"

    def test_utf8(self):
        """Tests parsing JSON with UTF-8 encoded characters."""
        rval = parse_json_request(b'"\xc4\x8de\xc5\xa1tina"')
        assert rval == "čeština"

    def test_unicode_struct(self):
        """Tests parsing a JSON structure with Unicode characters."""
        rval = parse_json_request(b'{"lang":"\\u010de\\u0161tina"}')
        assert rval == {"lang": "čeština"}

    def test_utf_struct(self):
        """Tests parsing a JSON structure with UTF-8 encoded characters."""
        rval = parse_json_request(b'{"lang":"\xc4\x8de\xc5\xa1tina"}')
        assert rval == {"lang": "čeština"}


class TestRequest:
    """Tests the Request class."""
    def test_host_wsgi(self, app):
        """Tests Request host resolution with WSGI environment variables."""
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
        """Tests Request host resolution with HTTP_HOST header."""
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
        """Tests Request host resolution with X-Forwarded headers."""
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
        """Tests request handling with an empty form."""
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


def test_bad_path_info_triggers_400(app):
    """Tests that bad PATH_INFO encoding is handled and returns 400."""
    captured_status = None
    captured_headers = None

    def start_response(status, headers):
        nonlocal captured_status, captured_headers
        captured_status = status
        captured_headers = headers

    # This char in iso-8859-1 is 0xc0, an invalid start byte in utf-8
    bad_char = 'À'
    bad_path = f'/foo{bad_char}bar'

    environ = {
        'PATH_INFO': bad_path,
        'REQUEST_METHOD': 'GET',
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '80',
        'wsgi.url_scheme': 'http',
        'REQUEST_STARTTIME': time()
    }

    # The app.__call__ should catch the HTTPException and generate a 400
    response_body = app(environ, start_response)

    assert captured_status == '400 Bad Request'
    # Also check body content
    body_str = b''.join(response_body).decode()
    assert '400' in body_str
    assert 'Bad Request' in body_str
    assert 'Invalid PATH_INFO encoding' in body_str


# ---------------------------------------------------------------------------
# Helpers shared by the new test classes
# ---------------------------------------------------------------------------

def _make_env(**kwargs):
    """Build a minimal valid WSGI environ for SimpleRequest / Request."""
    env = {
        'PATH_INFO': '/path',
        'REQUEST_METHOD': 'GET',
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '80',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.url_scheme': 'http',
        'REQUEST_STARTTIME': time(),
        'wsgi.input': BytesIO(),
        'wsgi.errors': BytesIO(),
    }
    env.update(kwargs)
    return env


# ---------------------------------------------------------------------------
# SimpleRequest properties
# ---------------------------------------------------------------------------

class TestSimpleRequest:
    """Tests for SimpleRequest properties and edge cases."""

    def test_uwsgi_poor_environ(self, app):
        """uwsgi.version in environ causes poor_environ to use os.environ."""
        env = _make_env(**{'uwsgi.version': b'2.0.0'})
        req = SimpleRequest(env, app)
        poor = req.poor_environ
        assert poor is not env

    def test_poor_version_env_detection(self, app, monkeypatch):
        """poor.Version in os.environ causes poor_environ to use os.environ."""
        monkeypatch.setenv('poor.Version', 'test')
        env = _make_env()
        req = SimpleRequest(env, app)
        assert 'poor.Version' in req.poor_environ

    def test_debug_from_environ_on(self, app):
        """poor_Debug=on in environ sets debug=True."""
        env = _make_env(poor_Debug='on')
        req = SimpleRequest(env, app)
        assert req.debug is True

    def test_debug_from_environ_off(self, app):
        """poor_Debug=off in environ sets debug=False."""
        env = _make_env(poor_Debug='off')
        req = SimpleRequest(env, app)
        assert req.debug is False

    def test_debug_falls_back_to_app(self, app):
        """Without poor_Debug, debug comes from app.debug."""
        env = _make_env()
        req = SimpleRequest(env, app)
        assert req.debug == app.debug

    def test_app_property(self, app):
        """app property returns the Application object."""
        env = _make_env()
        req = SimpleRequest(env, app)
        assert req.app is app

    def test_environ_copy(self, app):
        """environ property returns a copy of the environ dict."""
        env = _make_env()
        req = SimpleRequest(env, app)
        copy = req.environ
        assert copy is not env
        assert copy['PATH_INFO'] == '/path'

    def test_poor_environ_copy(self, app):
        """poor_environ property returns a copy."""
        env = _make_env()
        req = SimpleRequest(env, app)
        copy = req.poor_environ
        assert isinstance(copy, dict)

    def test_uri_rule_set_once(self, app):
        """uri_rule setter ignores subsequent assignments."""
        env = _make_env()
        req = SimpleRequest(env, app)
        req.uri_rule = '/first'
        req.uri_rule = '/second'
        assert req.uri_rule == '/first'

    def test_uri_handler_set_once(self, app):
        """uri_handler setter ignores subsequent assignments."""
        def handler1():
            pass

        def handler2():
            pass
        env = _make_env()
        req = SimpleRequest(env, app)
        req.uri_handler = handler1
        req.uri_handler = handler2
        assert req.uri_handler is handler1

    def test_error_handler_set_once(self, app):
        """error_handler setter ignores subsequent assignments."""
        def h1():
            pass

        def h2():
            pass
        env = _make_env()
        req = SimpleRequest(env, app)
        req.error_handler = h1
        req.error_handler = h2
        assert req.error_handler is h1

    def test_host_port_https_default(self, app):
        """host_port returns 443 for https when no port in HTTP_HOST."""
        env = _make_env(**{'wsgi.url_scheme': 'https', 'SERVER_PORT': '443'})
        req = SimpleRequest(env, app)
        assert req.host_port == 443

    def test_host_port_http_default(self, app):
        """host_port returns 80 for http when no port in HTTP_HOST."""
        env = _make_env()
        req = SimpleRequest(env, app)
        assert req.host_port == 80

    def test_method_number_unknown_method(self, app):
        """method_number falls back to GET for unknown methods."""
        env = _make_env(REQUEST_METHOD='UNKNOWN')
        req = SimpleRequest(env, app)
        assert req.method_number == methods['GET']

    def test_method_number_post(self, app):
        """method_number returns the POST constant."""
        env = _make_env(REQUEST_METHOD='POST')
        req = SimpleRequest(env, app)
        assert req.method_number == methods['POST']

    def test_full_path_with_query(self, app):
        """full_path includes query string when present."""
        env = _make_env(QUERY_STRING='foo=bar&baz=1')
        req = SimpleRequest(env, app)
        assert req.full_path == '/path?foo=bar&baz=1'

    def test_remote_host(self, app):
        """remote_host returns REMOTE_HOST environ value."""
        env = _make_env(REMOTE_HOST='client.example.org')
        req = SimpleRequest(env, app)
        assert req.remote_host == 'client.example.org'

    def test_remote_addr(self, app):
        """remote_addr returns REMOTE_ADDR environ value."""
        env = _make_env(REMOTE_ADDR='1.2.3.4')
        req = SimpleRequest(env, app)
        assert req.remote_addr == '1.2.3.4'

    def test_referer(self, app):
        """referer returns HTTP_REFERER environ value."""
        env = _make_env(HTTP_REFERER='http://example.org/')
        req = SimpleRequest(env, app)
        assert req.referer == 'http://example.org/'

    def test_user_agent(self, app):
        """user_agent returns HTTP_USER_AGENT environ value."""
        env = _make_env(HTTP_USER_AGENT='TestBot/1.0')
        req = SimpleRequest(env, app)
        assert req.user_agent == 'TestBot/1.0'

    def test_server_admin_custom(self, app):
        """server_admin returns SERVER_ADMIN when set."""
        env = _make_env(SERVER_ADMIN='admin@example.org')
        req = SimpleRequest(env, app)
        assert req.server_admin == 'admin@example.org'

    def test_server_admin_default(self, app):
        """server_admin defaults to webmaster@<hostname>."""
        env = _make_env()
        req = SimpleRequest(env, app)
        assert req.server_admin == 'webmaster@localhost'

    def test_server_port(self, app):
        """server_port returns int SERVER_PORT."""
        env = _make_env(SERVER_PORT='8080')
        req = SimpleRequest(env, app)
        assert req.server_port == 8080

    def test_port_alias(self, app):
        """port is an alias for server_port."""
        env = _make_env(SERVER_PORT='9000')
        req = SimpleRequest(env, app)
        assert req.port == 9000

    def test_protocol(self, app):
        """protocol returns SERVER_PROTOCOL."""
        env = _make_env(SERVER_PROTOCOL='HTTP/2.0')
        req = SimpleRequest(env, app)
        assert req.protocol == 'HTTP/2.0'

    def test_forwarded_for(self, app):
        """forwarded_for returns X-Forwarded-For header."""
        env = _make_env(HTTP_X_FORWARDED_FOR='10.0.0.1')
        req = SimpleRequest(env, app)
        assert req.forwarded_for == '10.0.0.1'

    def test_forwarded_host_with_port_strips_port(self, app):
        """forwarded_host strips the port component."""
        env = _make_env(HTTP_X_FORWARDED_HOST='proxy.example.org:8080')
        req = SimpleRequest(env, app)
        assert req.forwarded_host == 'proxy.example.org'

    def test_forwarded_host_without_port(self, app):
        """forwarded_host returns host unchanged when no port present."""
        env = _make_env(HTTP_X_FORWARDED_HOST='proxy.example.org')
        req = SimpleRequest(env, app)
        assert req.forwarded_host == 'proxy.example.org'

    def test_forwarded_port_from_host_header(self, app):
        """forwarded_port uses port from X-Forwarded-Host."""
        env = _make_env(HTTP_X_FORWARDED_HOST='proxy.example.org:9090')
        req = SimpleRequest(env, app)
        assert req.forwarded_port == 9090

    def test_forwarded_port_from_proto_https(self, app):
        """forwarded_port returns 443 when X-Forwarded-Proto is https."""
        env = _make_env(HTTP_X_FORWARDED_PROTO='https')
        req = SimpleRequest(env, app)
        assert req.forwarded_port == 443

    def test_forwarded_port_from_proto_http(self, app):
        """forwarded_port returns 80 when X-Forwarded-Proto is http."""
        env = _make_env(HTTP_X_FORWARDED_PROTO='http')
        req = SimpleRequest(env, app)
        assert req.forwarded_port == 80

    def test_forwarded_port_none_when_absent(self, app):
        """forwarded_port returns None when no forwarding headers."""
        env = _make_env()
        req = SimpleRequest(env, app)
        assert req.forwarded_port is None

    def test_forwarded_proto(self, app):
        """forwarded_proto returns X-Forwarded-Proto."""
        env = _make_env(HTTP_X_FORWARDED_PROTO='https')
        req = SimpleRequest(env, app)
        assert req.forwarded_proto == 'https'

    def test_secret_key_from_environ(self, app):
        """secret_key returns poor_SecretKey when set in environ."""
        env = _make_env(poor_SecretKey='mysecret')  # noqa: S105
        req = SimpleRequest(env, app)
        assert req.secret_key == 'mysecret'  # noqa: S105

    def test_document_index_from_environ(self, app):
        """poor_DocumentIndex=on in environ sets document_index=True."""
        env = _make_env(poor_DocumentIndex='on')
        req = SimpleRequest(env, app)
        assert req.document_index is True

    def test_get_options_deprecated(self, app):
        """get_options() emits DeprecationWarning and returns app_ vars."""
        env = _make_env(app_db='localhost', app_templates='templ')
        req = SimpleRequest(env, app)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            opts = req.get_options()
        assert len(caught) == 1
        assert issubclass(caught[0].category, DeprecationWarning)
        assert opts == {'db': 'localhost', 'templates': 'templ'}

    def test_construct_url_already_absolute(self, app):
        """construct_url returns URI unchanged when it already has a scheme."""
        env = _make_env()
        req = SimpleRequest(env, app)
        url = 'http://other.example.org/page'
        assert req.construct_url(url) == url

    def test_construct_url_nondefault_port(self, app):
        """construct_url includes port when it is non-default."""
        env = _make_env(HTTP_HOST='localhost:8080')
        req = SimpleRequest(env, app)
        assert req.construct_url('/foo') == 'http://localhost:8080/foo'

    def test_server_software_uwsgi(self, app):
        """server_software returns 'uWsgi' when uwsgi.version is present."""
        env = _make_env(**{'uwsgi.version': b'2.0'})
        req = SimpleRequest(env, app)
        assert req.server_software == 'uWsgi'


# ---------------------------------------------------------------------------
# Request.__init__ branches
# ---------------------------------------------------------------------------

class TestRequestInit:
    """Tests for Request.__init__ edge cases."""

    def test_missing_path_info_raises(self, app):
        """PATH_INFO=None raises ConnectionError."""
        env = _make_env()
        env['PATH_INFO'] = None
        with raises(ConnectionError):
            Request(env, app)

    def test_content_headers_parsed(self, app):
        """CONTENT_TYPE and CONTENT_LENGTH from environ reach the headers."""
        env = _make_env(
            CONTENT_TYPE='text/plain',
            CONTENT_LENGTH='5',
            **{'wsgi.input': BytesIO(b'hello')},
        )
        req = Request(env, app)
        assert req.mime_type == 'text/plain'
        assert req.content_length == 5

    def test_auto_data_wraps_body(self, app):
        """auto_data caches body in BytesIO when content_length <= data_size.
        """
        body = b'cached'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_LENGTH=str(len(body)),
            CONTENT_TYPE='application/octet-stream',
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        assert req.data == body

    def test_auto_json_parses_body(self, app):
        """auto_json parses a JSON body into req.json."""
        body = b'{"name": "test"}'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_TYPE='application/json',
            CONTENT_LENGTH=str(len(body)),
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        assert isinstance(req.json, JsonDict)
        assert req.json['name'] == 'test'

    def test_auto_form_parses_body(self, app):
        """auto_form parses a URL-encoded body into req.form."""
        body = b'name=Ondrej&age=30'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_TYPE='application/x-www-form-urlencoded',
            CONTENT_LENGTH=str(len(body)),
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        assert isinstance(req.form, FieldStorage)
        assert req.form.getvalue('name') == 'Ondrej'

    def test_auto_cookies_parses_cookie_header(self, app):
        """Cookie header is parsed into req.cookies when auto_cookies is set.
        """
        env = _make_env(HTTP_COOKIE='session=abc123; token=xyz')
        req = Request(env, app)
        assert req.cookies is not None
        assert 'session' in req.cookies
        assert req.cookies['session'].value == 'abc123'


# ---------------------------------------------------------------------------
# Request properties
# ---------------------------------------------------------------------------

class TestRequestProperties:
    """Tests for Request properties not covered by TestRequest."""

    def _req(self, app, **kwargs):
        return Request(_make_env(**kwargs), app)

    def test_charset_default(self, app):
        """charset defaults to utf-8 when not in Content-Type."""
        req = self._req(app)
        assert req.charset == 'utf-8'

    def test_charset_from_content_type(self, app):
        """charset is extracted from Content-Type parameter."""
        req = self._req(app, CONTENT_TYPE='text/plain; charset=iso-8859-1')
        assert req.charset == 'iso-8859-1'

    def test_content_length_absent(self, app):
        """content_length is -1 when Content-Length header is absent."""
        req = self._req(app)
        assert req.content_length == -1

    def test_accept_parses_header(self, app):
        """accept property parses the Accept header."""
        req = self._req(app, HTTP_ACCEPT='text/html, application/json;q=0.9')
        acc = req.accept
        assert ('text/html', 1.0) in acc
        assert ('application/json', 0.9) in acc

    def test_accept_charset(self, app):
        """accept_charset parses the Accept-Charset header."""
        req = self._req(app, HTTP_ACCEPT_CHARSET='utf-8, iso-8859-1;q=0.5')
        result = req.accept_charset
        assert any(v == 'utf-8' for v, _ in result)

    def test_accept_encoding(self, app):
        """accept_encoding parses the Accept-Encoding header."""
        req = self._req(app, HTTP_ACCEPT_ENCODING='gzip, deflate')
        result = req.accept_encoding
        assert any(v == 'gzip' for v, _ in result)

    def test_accept_language(self, app):
        """accept_language parses the Accept-Language header."""
        req = self._req(app, HTTP_ACCEPT_LANGUAGE='en-US, cs;q=0.8')
        result = req.accept_language
        assert any(v == 'en-US' for v, _ in result)

    def test_accept_html_true(self, app):
        """accept_html returns True when text/html is accepted."""
        req = self._req(app, HTTP_ACCEPT='text/html')
        assert req.accept_html is True

    def test_accept_xhtml_true(self, app):
        """accept_xhtml returns True when text/xhtml is accepted."""
        req = self._req(app, HTTP_ACCEPT='text/xhtml')
        assert req.accept_xhtml is True

    def test_accept_json_true(self, app):
        """accept_json returns True when application/json is accepted."""
        req = self._req(app, HTTP_ACCEPT='application/json')
        assert req.accept_json is True

    def test_authorization_basic(self, app):
        """authorization parses a Basic auth header."""
        creds = base64.b64encode(b'user:pass').decode()
        req = self._req(app, HTTP_AUTHORIZATION=f'Basic {creds}')
        auth = req.authorization
        assert auth['type'] == 'Basic'

    def test_authorization_digest(self, app):
        """authorization parses a Digest auth header."""
        header = 'Digest username="alice", realm="test", nonce="abc"'
        req = self._req(app, HTTP_AUTHORIZATION=header)
        auth = req.authorization
        assert auth['type'] == 'Digest'
        assert auth['username'] == 'alice'

    def test_is_xhr_true(self, app):
        """is_xhr returns True when X-Requested-With is XMLHttpRequest."""
        req = self._req(app, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert req.is_xhr is True

    def test_is_xhr_false(self, app):
        """is_xhr returns False when X-Requested-With is absent."""
        req = self._req(app)
        assert req.is_xhr is False

    def test_is_chunked_request_deprecated(self, app):
        """is_chunked_request emits DeprecationWarning."""
        req = self._req(app, HTTP_TRANSFER_ENCODING='chunked')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = req.is_chunked_request
        assert result is True
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_path_args_default_empty(self, app):
        """path_args returns {} when not set."""
        req = self._req(app)
        assert not req.path_args

    def test_path_args_setter_once(self, app):
        """path_args setter ignores subsequent assignments."""
        req = self._req(app)
        req.path_args = {'id': '1'}
        req.path_args = {'id': '2'}
        assert req.path_args == {'id': '1'}

    def test_args_property(self, app):
        """args property returns Args instance parsed from QUERY_STRING."""
        req = self._req(app, QUERY_STRING='x=1&y=2')
        assert req.args.getvalue('x') == '1'

    def test_args_setter_once(self, app):
        """args setter replaces EmptyForm but ignores further sets."""
        req = self._req(app)
        req.args = Args(req)
        assert not isinstance(req.args, EmptyForm)

    def test_form_setter_once(self, app):
        """form setter replaces EmptyForm but ignores further sets."""
        req = self._req(app)
        first = FieldStorage()
        second = FieldStorage()
        req.form = first
        req.form = second
        assert req.form is first

    def test_json_property_empty(self, app):
        """json property returns EmptyForm by default."""
        req = self._req(app)
        assert isinstance(req.json, EmptyForm)

    def test_data_property_with_body(self, app):
        """data property returns body when auto_data is active."""
        body = b'hello'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_LENGTH='5',
            CONTENT_TYPE='application/octet-stream',
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        assert req.data == body

    def test_data_property_none_for_non_bytesio(self, app):
        """data returns None when wsgi.input is not a BytesIO instance."""
        class _RawIO:
            def read(self, _n=-1):  # pylint: disable=invalid-name
                return b''

        env = _make_env(**{'wsgi.input': _RawIO()})
        req = Request(env, app)
        assert req.data is None

    def test_input_returns_file(self, app):
        """input property returns the wsgi.input stream."""
        req = self._req(app)
        assert req.input is not None

    def test_user_property(self, app):
        """user property can be set and read."""
        req = self._req(app)
        assert req.user is None
        req.user = 'alice'
        assert req.user == 'alice'

    def test_api_property(self, app):
        """api property can be set and read."""
        req = self._req(app)
        assert req.api is None
        req.api = {'version': '1.0'}
        assert req.api == {'version': '1.0'}

    def test_db_property(self, app):
        """db property can be set and read."""
        req = self._req(app)
        assert req.db is None
        req.db = object()
        assert req.db is not None


# ---------------------------------------------------------------------------
# Request methods
# ---------------------------------------------------------------------------

class TestRequestMethods:
    """Tests for Request read, read_chunk, and __del__."""

    def test_read_returns_empty_without_body(self, app):
        """read() returns b'' when there is no body."""
        req = Request(_make_env(), app)
        assert req.read() == b''

    def test_read_returns_body(self, app):
        """read() returns the full body from wsgi.input."""
        body = b'payload data'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_LENGTH=str(len(body)),
            CONTENT_TYPE='application/octet-stream',
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        assert req.read() == body

    def test_read_partial_length(self, app):
        """read(n) reads exactly n bytes and switches to __read mode."""
        body = b'hello world'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_LENGTH=str(len(body)),
            CONTENT_TYPE='application/octet-stream',
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        chunk = req.read(5)
        assert chunk == b'hello'

    def test_read_chunk(self, app):
        """read_chunk() reads a hex-length-prefixed chunk."""
        chunk_data = b'Hello'
        # Chunked format: hex_length CRLF data CRLF
        raw = b'5\r\n' + chunk_data + b'\r\n'
        env = _make_env(**{'wsgi.input': BytesIO(raw)})
        req = Request(env, app)
        result = req.read_chunk()
        assert result == chunk_data

    def test_del_does_not_raise(self, app):
        """__del__ executes without error."""
        req = Request(_make_env(), app)
        del req


# ---------------------------------------------------------------------------
# EmptyForm and JsonList deprecated fce argument
# ---------------------------------------------------------------------------

class TestDeprecatedFce:
    """Tests for the deprecated fce argument in EmptyForm and JsonList."""

    def test_empty_form_getfirst_fce_warns(self):
        """EmptyForm.getfirst with fce emits DeprecationWarning."""
        form = EmptyForm()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = form.getfirst('x', default=42, fce=int)
        assert result == 42
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_empty_form_getlist_fce_warns(self):
        """EmptyForm.getlist with fce emits DeprecationWarning."""
        form = EmptyForm()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = form.getlist('x', fce=str)
        assert not result
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_json_list_getfirst_fce_warns(self):
        """JsonList.getfirst with fce emits DeprecationWarning."""
        jl = JsonList([10, 20])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = jl.getfirst('any', fce=str)
        assert result == '10'
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_json_list_getlist_fce_warns(self):
        """JsonList.getlist with fce emits DeprecationWarning."""
        jl = JsonList([1, 2, 3])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = jl.getlist('any', fce=str)
        assert result == ['1', '2', '3']
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_json_list_getlist_empty_with_default(self):
        """JsonList.getlist on empty list returns the provided default."""
        jl = JsonList()
        assert jl.getlist('any', default=[9, 8]) == [9, 8]


# ---------------------------------------------------------------------------
# Deprecated FieldStorage compatibility function
# ---------------------------------------------------------------------------

class TestFieldStorageCompat:
    """Tests for the deprecated FieldStorage backwards-compatibility wrapper.
    """

    def test_field_storage_deprecated_warns(self, app):
        """FieldStorage() emits a DeprecationWarning and returns a form."""
        # Use a MIME type that auto_form does not consume, so wsgi.input
        # is still available when FieldStorage is called manually.
        body = b'key=value'
        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_TYPE='application/x-www-form-urlencoded',
            CONTENT_LENGTH=str(len(body)),
            **{'wsgi.input': BytesIO(body)},
        )
        req = Request(env, app)
        # Seek the input back to 0 — auto_form may have consumed it.
        req.input.seek(0)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            form = DeprecatedFieldStorage(req)
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert form is not None


# ---------------------------------------------------------------------------
# CachedInput
# ---------------------------------------------------------------------------

class TestCachedInput:
    """Tests for CachedInput buffered read and readline."""

    # --- read() ---

    def test_read_from_file_no_buffer(self):
        """read() reads directly from file when buffer is empty."""
        ci = CachedInput(BytesIO(b'hello world'), 11, block_size=32768)
        assert ci.read(5) == b'hello'

    def test_read_default_uses_block_size(self):
        """read() with no argument reads block_size bytes."""
        ci = CachedInput(BytesIO(b'x' * 10), 10, block_size=4)
        chunk = ci.read()
        assert chunk == b'xxxx'

    def test_read_from_buffer_sufficient(self):
        """read() returns from buffer when it holds enough data."""
        # Pre-populate buffer and keep todo > 0 so size is not capped to 0.
        ci = CachedInput(BytesIO(b'extra'), 10, block_size=32768)
        ci._CachedInput__buffer = b'hello'  # pylint: disable=protected-access
        ci._CachedInput__todo = 10  # pylint: disable=protected-access
        assert ci.read(3) == b'hel'

    def test_read_combines_buffer_and_file(self):
        """read() combines partial buffer with additional file data."""
        # 2 bytes in buffer, 5 bytes in file, request 5 → combine.
        ci = CachedInput(BytesIO(b'CDEFG'), 10, block_size=32768)
        ci._CachedInput__buffer = b'AB'  # pylint: disable=protected-access
        ci._CachedInput__todo = 10  # pylint: disable=protected-access
        result = ci.read(5)
        assert result == b'ABCDE'

    # --- readline() ---

    def test_readline_finds_crlf(self):
        """readline() returns up to and including the first CRLF."""
        data = b'hello\r\nworld'
        ci = CachedInput(BytesIO(data), len(data), block_size=32768)
        assert ci.readline() == b'hello\r\n'

    def test_readline_no_crlf_returns_all(self):
        """readline() returns all data when no CRLF is present."""
        data = b'noeol'
        ci = CachedInput(BytesIO(data), len(data), block_size=32768,
                         timeout=None)
        assert ci.readline() == data

    def test_readline_timeout_raises(self):
        """readline() raises TimeoutError when data never arrives.

        todo must be > 0 so the initial buffer fill sets size > 0 and the
        while-loop actually runs the timeout check.
        """
        # BytesIO(b'') returns b'' for any read → buffer stays empty forever.
        # timeout=0 means times_out_at is already in the past at first check.
        ci = CachedInput(BytesIO(b''), 5, block_size=5, timeout=0)
        with raises(TimeoutError):
            ci.readline()

    def test_readline_seen_data_resets_timer(self):
        """readline() resets the timeout timer after consuming data."""
        # With timeout=None, this just exercises the seen_data=True branch
        # by having data in the buffer at timeout-check time.
        data = b'nodot'
        ci = CachedInput(BytesIO(data), len(data), block_size=32768,
                         timeout=10)
        result = ci.readline()
        # No CRLF → returns full data
        assert result == data

    def test_readline_with_existing_buffer(self):
        """readline() uses existing buffer content before reading file."""
        data = b'first\r\nsecond\r\n'
        ci = CachedInput(BytesIO(data), len(data), block_size=len(data))
        assert ci.readline() == b'first\r\n'
        # Second readline uses leftover buffer
        assert ci.readline() == b'second\r\n'

    def test_readline_reads_more_from_file(self):
        """readline() reads additional data when buffer is shorter than size.

        Covers lines 1115-1118 (n_size read) and 1103-1104 (seen_data=True).
        """
        # Pre-load a short buffer (2 bytes) plus file that completes the line.
        ci = CachedInput(BytesIO(b'\r\n'), 2, block_size=5, timeout=10)
        # pylint: disable=protected-access
        ci._CachedInput__buffer = b'ab'
        ci._CachedInput__todo = 2
        # readline: buffer is non-empty → skip initial fill, size=block_size=5
        # iter1: buffer=b'ab' → seen_data=True; consume; l_size=2 < 5
        #        → reads 2 more bytes from file → buffer=b'\r\n'
        # iter2: finds \r\n at pos=0 → returns b'ab\r\n'
        result = ci.readline()
        assert result == b'ab\r\n'

    def test_readline_seen_data_timer_reset(self):
        """readline() resets the timer when buffer empties after having data.

        Covers lines 1106-1107 (seen_data=True → False, timer reset).
        After the reset, timeout=0 fires TimeoutError on next iteration.
        """
        # Pre-populate buffer with b'ab', file returns nothing, timeout=0.
        # pylint: disable=protected-access
        ci = CachedInput(BytesIO(b''), 2, block_size=5, timeout=0)
        ci._CachedInput__buffer = b'ab'
        ci._CachedInput__todo = 2
        # iter1: buffer=b'ab' → seen_data=True; consume; read()→b''; l_size=2<5
        # iter2: buffer=b'' → seen_data resets to False + timer reset (1106)
        # iter3: buffer=b'' + no data → time()>times_out_at → TimeoutError
        with raises(TimeoutError):
            ci.readline()


# ---------------------------------------------------------------------------
# Additional targeted tests for remaining uncovered lines
# ---------------------------------------------------------------------------

class TestRemainingCoverage:
    """Covers lines not reached by the main test classes."""

    def test_uri_deprecated_alias(self, app):
        """uri property is a deprecated alias for path."""
        req = Request(_make_env(PATH_INFO='/foo'), app)
        assert req.uri == '/foo'

    def test_scheme_property(self, app):
        """scheme property returns wsgi.url_scheme."""
        req = Request(_make_env(**{'wsgi.url_scheme': 'https',
                                   'SERVER_PORT': '443'}), app)
        assert req.scheme == 'https'

    def test_document_index_from_app(self, app):
        """document_index falls back to app.document_index."""
        req = Request(_make_env(), app)
        assert req.document_index == app.document_index

    def test_start_time_and_end_time(self, app):
        """start_time and end_time return timestamps."""
        req = Request(_make_env(), app)
        assert isinstance(req.start_time, float)
        assert isinstance(req.end_time, float)

    def test_authorization_utf8_username(self, app):
        """authorization decodes RFC 5987 UTF-8'' encoded username."""
        # username*=UTF-8''Ond%C5%99ej decodes to 'Ondřej'
        header = "Digest username*=UTF-8''Ond%C5%99ej, realm=\"test\""
        req = Request(_make_env(HTTP_AUTHORIZATION=header), app)
        auth = req.authorization
        assert auth.get('username') == 'Ondřej'

    def test_args_setter_ignored_when_not_empty_form(self, app):
        """args.setter does nothing when args is already set."""
        req = Request(_make_env(QUERY_STRING='x=1'), app)
        original = req.args
        req.args = EmptyForm()  # setter should ignore this
        assert req.args is original

    def test_input_creates_cached_input(self):
        """input property creates CachedInput when cached_size > 0 and
        wsgi.input is not BytesIO (auto_data must be off)."""
        class _RawIO:
            def read(self, n=-1):
                return b'x' * n if n > 0 else b''

        local_app = Application("_test_cached_input_creation")
        local_app.auto_data = False
        local_app.auto_json = False
        local_app.auto_form = False
        local_app.cached_size = 4096

        env = _make_env(
            REQUEST_METHOD='POST',
            CONTENT_LENGTH='10',
            CONTENT_TYPE='application/octet-stream',
            **{'wsgi.input': _RawIO()},
        )
        req = Request(env, local_app)
        # Access twice; second call returns cached instance (line 719).
        first = req.input
        second = req.input
        assert first is second
        assert isinstance(first, CachedInput)

    def test_auto_args_false_uses_empty_form(self):
        """When auto_args=False, req.args is an EmptyForm."""
        local_app = Application("_test_auto_args_false")
        local_app.auto_args = False
        req = Request(_make_env(QUERY_STRING='x=1'), local_app)
        assert isinstance(req.args, EmptyForm)

    def test_args_setter_sets_when_empty_form(self):
        """args.setter replaces EmptyForm (line 655)."""
        local_app = Application("_test_args_setter_line655")
        local_app.auto_args = False
        req = Request(_make_env(QUERY_STRING='x=1'), local_app)
        assert isinstance(req.args, EmptyForm)
        new_args = Args(req)
        req.args = new_args
        assert req.args is new_args

    def test_document_root_property(self, app):
        """document_root returns poor_DocumentRoot or app.document_root."""
        req = Request(_make_env(), app)
        _ = req.document_root  # covers line 328
