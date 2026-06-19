"""Unit tests for poorwsgi/results.py — default HTTP handlers."""
# pylint: disable=too-many-lines
import os
import tempfile
from collections import defaultdict
from hashlib import sha256
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from poorwsgi import Application
from poorwsgi.request import Request
from poorwsgi.response import HTTPException, NotModifiedResponse
from poorwsgi.results import (
    bad_request,
    debug_info,
    directory_index,
    forbidden,
    hbytes,
    html_escape,
    human_methods_,
    handlers_view,
    internal_server_error,
    method_not_allowed,
    not_found,
    not_implemented,
    not_modified,
    unauthorized,
)
from poorwsgi.state import (
    HTTP_BAD_REQUEST,
    HTTP_FORBIDDEN,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_METHOD_NOT_ALLOWED,
    HTTP_NOT_FOUND,
    HTTP_NOT_IMPLEMENTED,
    HTTP_NOT_MODIFIED,
    HTTP_UNAUTHORIZED,
    METHOD_ALL,
    METHOD_GET,
    METHOD_POST,
)

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name


@pytest.fixture(scope="module")
def digest_app():
    """Application configured for Digest authentication."""
    app = Application("results_test")
    app.secret_key = "testsecret"  # noqa: S105
    app.auth_type = "Digest"
    return app


def _call(res):
    """Call a Response and return (status_code, headers_dict, body_bytes)."""
    status_holder = []
    hdrs = {}

    def start_response(status, headers):
        status_holder.append(int(status.split()[0]))
        hdrs.update(headers)

    body = b"".join(res(start_response))
    return status_holder[0], hdrs, body


def _make_req(**kwargs):
    """Return a MagicMock request with sensible defaults."""
    req = MagicMock()
    req.method = kwargs.get("method", "GET")
    req.uri = kwargs.get("uri", "/test")
    req.server_admin = kwargs.get("server_admin", "admin@example.com")
    req.debug = kwargs.get("debug", False)
    req.headers = MagicMock()
    req.headers.get = lambda k, d=None: kwargs.get(f"hdr_{k}", d)
    req.headers.items = lambda: kwargs.get("headers_items", {}).items()
    req.path = kwargs.get("path", req.uri)
    return req


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

class TestHtmlEscape:
    """html_escape must neutralise all five HTML special characters."""

    def test_ampersand(self):
        assert html_escape("a&b") == "a&amp;b"

    def test_double_quote(self):
        assert html_escape('"value"') == "&quot;value&quot;"

    def test_single_quote(self):
        assert html_escape("it's") == "it&apos;s"

    def test_less_than(self):
        assert html_escape("<tag>") == "&lt;tag&gt;"

    def test_greater_than(self):
        assert html_escape("a>b") == "a&gt;b"

    def test_plain_text_unchanged(self):
        assert html_escape("hello world 123") == "hello world 123"

    def test_xss_payload(self):
        raw = '<script>alert("xss")</script>'
        escaped = html_escape(raw)
        assert "<script>" not in escaped
        assert "&lt;script&gt;" in escaped

    def test_multiple_specials(self):
        assert html_escape("a&b<c>d") == "a&amp;b&lt;c&gt;d"


class TestHbytes:
    """hbytes converts raw byte counts to (value, unit) pairs."""

    def test_bytes_under_1000(self):
        val, unit = hbytes(512)
        assert unit == ""
        assert val == 512

    def test_exactly_1000(self):
        val, unit = hbytes(1000)
        assert unit == ""
        assert val == 1000

    def test_kilobytes(self):
        val, unit = hbytes(1024)
        assert unit == "k"
        assert val == pytest.approx(1.0)

    def test_megabytes(self):
        _val, unit = hbytes(2_000_000)
        assert unit == "M"

    def test_gigabytes(self):
        _val, unit = hbytes(2_000_000_000)
        assert unit == "G"


class TestHumanMethods:
    """human_methods_ converts a bitmask to a human-readable string."""

    def test_method_all_constant(self):
        assert human_methods_(METHOD_ALL) == "ALL"

    def test_single_get(self):
        result = human_methods_(METHOD_GET)
        assert "GET" in result

    def test_get_and_post(self):
        result = human_methods_(METHOD_GET | METHOD_POST)
        assert "GET" in result
        assert "POST" in result


class TestHandlersView:
    """handlers_view flattens and sorts a handler table."""

    def test_empty_table(self):
        assert not handlers_view({})

    def test_single_handler(self):
        def my_handler(req):  # pylint: disable=unused-argument
            pass
        table = {"/path": {METHOD_GET: my_handler}}
        result = handlers_view(table)
        assert len(result) == 1
        url, _, handler = result[0]
        assert url == "/path"
        assert handler is my_handler

    def test_sorted_by_url(self):
        def h(req):  # pylint: disable=unused-argument
            pass
        table = {"/z": {METHOD_GET: h}, "/a": {METHOD_GET: h}}
        result = handlers_view(table)
        assert result[0][0] == "/a"
        assert result[1][0] == "/z"

    def test_no_sort(self):
        def h(req):  # pylint: disable=unused-argument
            pass
        table = {"/z": {METHOD_GET: h}, "/a": {METHOD_GET: h}}
        result = handlers_view(table, sort=False)
        assert [r[0] for r in result] == ["/z", "/a"]


# ---------------------------------------------------------------------------
# HTTP response handlers
# ---------------------------------------------------------------------------

class TestNotModified:
    """not_modified → HTTP 304 Not Modified (RFC 7232 §4.1)."""

    def test_returns_304_response(self):
        """Handler must return a NotModifiedResponse."""
        req = _make_req()
        res = not_modified(req)
        assert isinstance(res, NotModifiedResponse)

    def test_status_code_304(self):
        """The WSGI status string must be '304 Not Modified'."""
        req = _make_req()
        res = not_modified(req)
        status, _, _ = _call(res)
        assert status == HTTP_NOT_MODIFIED

    def test_etag_stored_in_response(self):
        """ETag from request headers must be stored in the response headers."""
        req = _make_req(hdr_ETag='"abc123"')
        res = not_modified(req)
        assert '"abc123"' in str(res.headers)

    def test_date_stored_in_response(self):
        """Date header must be set (RFC 7231 §7.1.1)."""
        req = _make_req()
        res = not_modified(req)
        assert "Date" in str(res.headers)


class TestBadRequest:
    """bad_request → HTTP 400 Bad Request."""

    def test_status_code(self):
        res = bad_request(_make_req())
        assert res.status_code == HTTP_BAD_REQUEST

    def test_status_line(self):
        status, _, _ = _call(bad_request(_make_req()))
        assert status == HTTP_BAD_REQUEST

    def test_content_type_html(self):
        _, hdrs, _ = _call(bad_request(_make_req()))
        assert "text/html" in hdrs.get("Content-Type", "")

    def test_method_in_body(self):
        _, _, body = _call(bad_request(_make_req(method="DELETE")))
        assert b"DELETE" in body

    def test_uri_in_body(self):
        _, _, body = _call(bad_request(_make_req(uri="/my/path")))
        assert b"/my/path" in body

    def test_xss_in_uri_escaped(self):
        """URI with <script> must be HTML-escaped, not injected raw."""
        xss_uri = '/path<script>alert(1)</script>'
        _, _, body = _call(bad_request(_make_req(uri=xss_uri)))
        assert b"<script>" not in body
        assert b"&lt;script&gt;" in body

    def test_error_message_included(self):
        """Optional error argument must appear in the body."""
        req = _make_req()
        _, _, body = _call(bad_request(req, error="bad query"))
        assert b"bad query" in body

    def test_path_fallback_on_exception(self):
        """If req.path raises HTTPException, body still renders."""
        req = _make_req()
        type(req).path = PropertyMock(
            side_effect=HTTPException(HTTP_BAD_REQUEST))
        res = bad_request(req)
        assert res.status_code == HTTP_BAD_REQUEST


class TestUnauthorized:
    """unauthorized → HTTP 401 Unauthorized (RFC 7235 §3.1)."""

    def _req(self, app=None):
        req = _make_req(method="GET", uri="/secret")
        if app:
            req.app = app
            req.server_hostname = "localhost"
            req.secret_key = "testsecret"  # noqa: S105
            req.user_agent = "TestBrowser/1.0"
        return req

    def test_status_code_without_auth_type(self):
        """Without app.auth_type set, 401 is returned with no challenge."""
        req = self._req()
        req.app.auth_type = None
        res = unauthorized(req)
        assert res.status_code == HTTP_UNAUTHORIZED

    def test_no_www_auth_header_without_digest(self):
        """Non-Digest auth type → no WWW-Authenticate header."""
        req = self._req()
        req.app.auth_type = None
        _, hdrs, _ = _call(unauthorized(req))
        assert "WWW-Authenticate" not in hdrs

    def test_error_arg_logs_warning(self):
        """error argument is logged and still returns 401."""
        req = self._req()
        req.app.auth_type = None
        res = unauthorized(req, error="bad token")
        assert res.status_code == HTTP_UNAUTHORIZED

    def test_digest_requires_realm(self, digest_app):
        """Digest auth without realm → RuntimeError (RFC 7616 requirement)."""
        req = self._req(app=digest_app)
        with pytest.raises(RuntimeError, match="realm"):
            unauthorized(req)

    def test_digest_www_authenticate_present(self, digest_app):
        """Digest auth with realm → WWW-Authenticate required by RFC 7235."""
        req = self._req(app=digest_app)
        _, hdrs, _ = _call(unauthorized(req, realm="Protected Zone"))
        www_auth = hdrs.get("WWW-Authenticate", "")
        assert www_auth.startswith("Digest")
        assert 'realm="Protected Zone"' in www_auth

    def test_digest_www_authenticate_fields(self, digest_app):
        """WWW-Authenticate must include nonce, opaque, algorithm."""
        req = self._req(app=digest_app)
        _, hdrs, _ = _call(unauthorized(req, realm="Zone"))
        www_auth = hdrs.get("WWW-Authenticate", "")
        assert "nonce=" in www_auth
        assert "opaque=" in www_auth
        assert "algorithm=" in www_auth

    def test_digest_stale_flag(self, digest_app):
        """stale=True adds stale=true to WWW-Authenticate (RFC 7616 §3.4)."""
        req = self._req(app=digest_app)
        _, hdrs, _ = _call(unauthorized(req, realm="Zone", stale=True))
        assert "stale=true" in hdrs.get("WWW-Authenticate", "")

    def test_digest_no_stale_flag_by_default(self, digest_app):
        """Without stale=True, stale=true must NOT appear."""
        req = self._req(app=digest_app)
        _, hdrs, _ = _call(unauthorized(req, realm="Zone"))
        assert "stale=true" not in hdrs.get("WWW-Authenticate", "")

    def test_digest_qop_in_header(self, digest_app):
        """When app.auth_qop is set, qop= must appear in WWW-Authenticate."""
        req = self._req(app=digest_app)
        _, hdrs, _ = _call(unauthorized(req, realm="Zone"))
        assert "qop=" in hdrs.get("WWW-Authenticate", "")

    def test_opaque_is_sha256_of_hostname(self, digest_app):
        """opaque must equal sha256(server_hostname)."""
        req = self._req(app=digest_app)
        req.server_hostname = "myserver.example.com"
        _, hdrs, _ = _call(unauthorized(req, realm="Zone"))
        expected = sha256("myserver.example.com".encode()).hexdigest()
        assert expected in hdrs.get("WWW-Authenticate", "")


class TestForbidden:
    """forbidden → HTTP 403 Forbidden."""

    def test_error_arg_logs_warning(self):
        """error argument is logged and still returns 403."""
        assert forbidden(_make_req(), error="ip banned").status_code \
            == HTTP_FORBIDDEN

    def test_status_code(self):
        res = forbidden(_make_req())
        assert res.status_code == HTTP_FORBIDDEN

    def test_content_type_html(self):
        _, hdrs, _ = _call(forbidden(_make_req()))
        assert "text/html" in hdrs.get("Content-Type", "")

    def test_uri_in_body(self):
        _, _, body = _call(forbidden(_make_req(uri="/secret")))
        assert b"/secret" in body

    def test_xss_in_uri_escaped(self):
        """Angle brackets in URI must be escaped in the 403 body."""
        xss_uri = '/path"><img src=x onerror=alert(1)>'
        _, _, body = _call(forbidden(_make_req(uri=xss_uri)))
        assert b"<img" not in body
        assert b"&lt;img" in body


class TestNotFound:
    """not_found → HTTP 404 Not Found."""

    def test_error_arg_logs_warning(self):
        """error argument is logged and still returns 404."""
        assert not_found(_make_req(), error="gone").status_code \
            == HTTP_NOT_FOUND

    def test_status_code(self):
        assert not_found(_make_req()).status_code == HTTP_NOT_FOUND

    def test_content_type_html(self):
        _, hdrs, _ = _call(not_found(_make_req()))
        assert "text/html" in hdrs.get("Content-Type", "")

    def test_uri_in_body(self):
        _, _, body = _call(not_found(_make_req(uri="/missing.html")))
        assert b"/missing.html" in body

    def test_xss_in_uri_escaped(self):
        """Raw HTML tags in URI must be escaped in the 404 body."""
        xss_uri = '/path<b onmouseover=alert(1)>text</b>'
        _, _, body = _call(not_found(_make_req(uri=xss_uri)))
        assert b"<b " not in body
        assert b"&lt;b " in body


class TestMethodNotAllowed:
    """method_not_allowed → HTTP 405 Method Not Allowed."""

    def test_error_arg_logs_warning(self):
        """error argument is logged and still returns 405."""
        assert method_not_allowed(_make_req(), error="method X").status_code \
            == HTTP_METHOD_NOT_ALLOWED

    def test_status_code(self):
        assert method_not_allowed(_make_req()).status_code \
            == HTTP_METHOD_NOT_ALLOWED

    def test_content_type_html(self):
        _, hdrs, _ = _call(method_not_allowed(_make_req()))
        assert "text/html" in hdrs.get("Content-Type", "")

    def test_method_in_body(self):
        _, _, body = _call(method_not_allowed(_make_req(method="PATCH")))
        assert b"PATCH" in body

    def test_uri_in_body(self):
        _, _, body = _call(
            method_not_allowed(_make_req(uri="/api/v1"))
        )
        assert b"/api/v1" in body

    def test_xss_in_uri_escaped(self):
        """Script tag in URI must be escaped in the 405 body."""
        _, _, body = _call(
            method_not_allowed(_make_req(uri='/<script>x</script>'))
        )
        assert b"<script>" not in body
        assert b"&lt;script&gt;" in body


class TestNotImplemented:
    """not_implemented → HTTP 501 Not Implemented."""

    def test_error_arg_logs_warning(self):
        """error argument is logged and still returns 501."""
        res = not_implemented(_make_req(), error="handler missing")
        assert res.status_code == HTTP_NOT_IMPLEMENTED

    def test_status_code(self):
        assert not_implemented(_make_req()).status_code \
            == HTTP_NOT_IMPLEMENTED

    def test_content_type_html(self):
        _, hdrs, _ = _call(not_implemented(_make_req()))
        assert "text/html" in hdrs.get("Content-Type", "")

    def test_without_code_generic_message(self):
        _, _, body = _call(not_implemented(_make_req(uri="/api")))
        assert b"not implemented" in body.lower()

    def test_with_code_shows_code(self):
        _, _, body = _call(not_implemented(_make_req(uri="/api"), code=999))
        assert b"999" in body

    def test_with_code_shows_uri(self):
        _, _, body = _call(not_implemented(_make_req(uri="/api/ep"), code=999))
        assert b"/api/ep" in body


class TestInternalServerError:
    """internal_server_error → HTTP 500 Internal Server Error."""

    def _req(self, debug=False):
        req = _make_req(method="GET", uri="/boom", debug=debug)
        req.uri_handler = None
        req.uri_rule = ""
        req.remote_host = "client.example.com"
        req.remote_addr = "10.0.0.1"
        req.server_software = "TestServer/1.0"
        return req

    def test_status_code(self):
        res = internal_server_error(self._req())
        assert res.status_code == HTTP_INTERNAL_SERVER_ERROR

    def test_content_type_html(self):
        _, hdrs, _ = _call(internal_server_error(self._req()))
        assert "text/html" in hdrs.get("Content-Type", "")

    def test_without_debug_no_traceback(self):
        """Without debug mode, no traceback must leak in the response."""
        _, _, body = _call(internal_server_error(self._req(debug=False)))
        assert b"Traceback" not in body

    def test_with_debug_shows_request_info(self):
        """With debug enabled, URI and method details appear."""
        req = self._req(debug=True)
        req.uri = "/exploded"
        _, _, body = _call(internal_server_error(req))
        assert b"/exploded" in body
        assert b"GET" in body

    def test_with_debug_shows_traceback_section(self):
        """With debug enabled, the Exception Traceback section is present."""
        _, _, body = _call(internal_server_error(self._req(debug=True)))
        assert b"Exception Traceback" in body

    def test_with_uri_handler(self):
        """Handler name and module should appear when uri_handler is set."""
        def my_view(req):  # pylint: disable=unused-argument
            pass
        req = self._req(debug=True)
        req.uri_handler = my_view
        _, _, body = _call(internal_server_error(req))
        assert b"my_view" in body

    def test_xss_in_uri_escaped(self):
        """URI is HTML-escaped even in the 500 debug page."""
        req = self._req(debug=True)
        req.uri = '/path<script>alert(1)</script>'
        _, _, body = _call(internal_server_error(req))
        assert b"<script>alert(1)</script>" not in body

    def test_active_exception_traceback(self):
        """When called inside an except block, the traceback is rendered."""
        req = self._req(debug=True)
        body = b""
        try:
            raise ValueError("intentional test error")
        except ValueError:
            _, _, body = _call(internal_server_error(req))
        assert b"intentional test error" in body


class TestDirectoryIndex:
    """directory_index → HTML directory listing (WSGI static file serving)."""

    def _req(self, root, uri="/files/", debug=False):
        req = MagicMock()
        req.document_root = root
        req.uri = uri
        req.debug = debug
        req.server_software = "TestServer/1.0"
        req.server_admin = "admin@example.com"
        return req

    def test_not_a_directory_raises(self):
        """Passing a file path instead of directory → HTTP 500."""
        with tempfile.NamedTemporaryFile() as f:
            req = self._req(root="/")
            with pytest.raises(HTTPException) as exc_info:
                directory_index(req, f.name)
            assert exc_info.value.status_code == HTTP_INTERNAL_SERVER_ERROR

    def test_returns_tuple(self):
        with tempfile.TemporaryDirectory() as d:
            result = directory_index(self._req(root="/"), d)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_content_type(self):
        with tempfile.TemporaryDirectory() as d:
            _, content_type, _ = directory_index(self._req(root="/"), d)
        assert "text/html" in content_type

    def test_last_modified_header(self):
        """Third element must be the Last-Modified header tuple."""
        with tempfile.TemporaryDirectory() as d:
            _, _, header = directory_index(self._req(root="/"), d)
        assert header[0] == "Last-Modified"
        # RFC 7231 §7.1.1: HTTP-date format
        assert "GMT" in header[1]

    def test_html_structure(self):
        """Response must be valid HTML with a listing table."""
        with tempfile.TemporaryDirectory() as d:
            content, _, _ = directory_index(self._req(root="/"), d)
        assert "<!DOCTYPE html>" in content
        assert "<table>" in content

    def test_regular_file_listed(self):
        """Regular files in the directory must appear in the listing."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "readme.txt"), "w",
                      encoding="utf-8") as f:
                f.write("")
            content, _, _ = directory_index(self._req(root="/"), d)
        assert "readme.txt" in content

    def test_dot_files_hidden(self):
        """Files starting with '.' (other than '..') must be excluded."""
        with tempfile.TemporaryDirectory() as d:
            for name in (".hidden", "visible.txt"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write("")
            content, _, _ = directory_index(self._req(root="/"), d)
        assert ".hidden" not in content
        assert "visible.txt" in content

    def test_backup_files_hidden(self):
        """Files ending with '~' (editor backups) must be excluded."""
        with tempfile.TemporaryDirectory() as d:
            for name in ("file.py~", "file.py"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write("")
            content, _, _ = directory_index(self._req(root="/"), d)
        assert "file.py~" not in content
        assert "file.py" in content

    def test_subdirectory_listed(self):
        """Subdirectories must appear with trailing slash."""
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "subdir"))
            content, _, _ = directory_index(self._req(root="/"), d)
        assert "subdir/" in content

    def test_parent_link_when_not_root(self):
        """Parent directory '..' link must appear when not at document root."""
        with tempfile.TemporaryDirectory() as d:
            req = self._req(root="/other/root", uri="/files/")
            content, _, _ = directory_index(req, d)
        assert ".." in content

    def test_no_parent_link_at_document_root(self):
        """'..' must NOT appear when the path IS the document root."""
        with tempfile.TemporaryDirectory() as d:
            req = self._req(root=d[:-1], uri="/")
            content, _, _ = directory_index(req, d)
        assert "../" not in content

    def test_unknown_extension_falls_back_to_octet_stream(self):
        """Files with unknown extensions use application/octet-stream."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "data.xyzzy"),
                      "w", encoding="utf-8") as f:
                f.write("x")
            content, _, _ = directory_index(self._req(root="/"), d)
        assert "octet-stream" in content

    def test_unreadable_file_skipped(self):
        """Files that fail os.access(R_OK) must not appear in the listing."""
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "secret.txt"),
                      "w", encoding="utf-8") as f:
                f.write("x")
            with patch("poorwsgi.results.os.access", return_value=False):
                content, _, _ = directory_index(self._req(root="/"), d)
        assert "secret.txt" not in content

    def test_xss_in_uri_escaped(self):
        """URI is HTML-escaped in the page title."""
        with tempfile.TemporaryDirectory() as d:
            req = self._req(root="/", uri='/<script>xss</script>/')
            content, _, _ = directory_index(req, d)
        assert "<script>xss</script>" not in content
        assert "&lt;script&gt;" in content

    def test_debug_shows_server_software(self):
        """In debug mode, server_software string appears in the footer."""
        with tempfile.TemporaryDirectory() as d:
            req = self._req(root="/", debug=True)
            content, _, _ = directory_index(req, d)
        assert "TestServer/1.0" in content

    def test_no_debug_hides_server_software(self):
        """Without debug, server_software must NOT leak into the page."""
        with tempfile.TemporaryDirectory() as d:
            req = self._req(root="/", debug=False)
            content, _, _ = directory_index(req, d)
        assert "TestServer/1.0" not in content


class TestDebugInfo:
    """debug_info → HTML debugging page (application introspection)."""

    @pytest.fixture(scope="class")
    def app_req(self):
        app = Application("results_debug")
        app.secret_key = "testsecret"  # noqa: S105

        env = defaultdict(str)
        env["PATH_INFO"] = "/debug-info"
        env["SERVER_PORT"] = "80"
        env["SERVER_NAME"] = "localhost"
        env["HTTP_HOST"] = "localhost"
        env["REQUEST_METHOD"] = "GET"
        req = Request(env, app)
        return req, app

    def test_returns_string(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert isinstance(result, str)

    def test_html_structure(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert "<!DOCTYPE html>" in result
        assert "<table" in result

    def test_route_table_section(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert "Route Table" in result

    def test_state_handlers_section(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert "State Handlers" in result

    def test_poor_variables_section(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert "Poor" in result

    def test_environ_section(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert "Environ" in result

    def test_headers_section(self, app_req):
        req, app = app_req
        result = debug_info(req, app)
        assert "Headers" in result

    def test_custom_route_appears(self, app_req):
        """A user-defined route must appear in the debug page."""
        req, app = app_req

        @app.route("/my/endpoint")
        def my_endpoint(r):  # pylint: disable=unused-argument
            return "ok"

        result = debug_info(req, app)
        assert "/my/endpoint" in result

    def test_user_state_handler_appears(self, app_req):
        """A user-defined state handler must be listed in state table."""
        req, app = app_req

        @app.http_state(HTTP_NOT_FOUND)
        def my_results_404(r, *_):  # pylint: disable=unused-argument
            return "not found"

        result = debug_info(req, app)
        assert "my_results_404" in result

    def test_before_after_handlers_listed(self, app_req):
        """Before and after handlers table must appear."""
        req, app = app_req

        def results_before(r):  # pylint: disable=unused-argument
            pass

        def results_after(r, res):  # pylint: disable=unused-argument
            return res

        app.add_before_response(results_before)
        app.add_after_response(results_after)
        result = debug_info(req, app)
        assert "results_before" in result
        assert "results_after" in result
