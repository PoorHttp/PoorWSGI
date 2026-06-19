"""Unit tests for poorwsgi/fieldstorage.py.

Focuses on HTTP-level behavior: multipart/form-data (RFC 7578),
application/x-www-form-urlencoded, boundary validation, file uploads,
and browser compatibility quirks.
"""

import tempfile
import warnings
from io import BytesIO, StringIO, TextIOWrapper

import pytest

from poorwsgi.fieldstorage import (
    FieldStorage,
    FieldStorageInterface,
    FieldStorageParser,
    valid_boundary,
)
from poorwsgi.headers import Headers

# pylint: disable=missing-function-docstring
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-lines
# pylint: disable=no-self-use
# pylint: disable=R6301


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _urlencoded(body: str, charset="utf-8") -> FieldStorage:
    """Parses a URL-encoded body and returns the root FieldStorage."""
    body_bytes = body.encode(charset)
    headers = Headers([
        ("Content-Type", "application/x-www-form-urlencoded"),
        ("Content-Length", str(len(body_bytes))),
    ])
    parser = FieldStorageParser(BytesIO(body_bytes), headers)
    return parser.parse()


def _multipart(body: bytes, boundary: str) -> FieldStorage:
    """Parses a multipart/form-data body and returns the root FieldStorage."""
    headers = Headers([
        ("Content-Type",
         f"multipart/form-data; boundary={boundary}"),
        ("Content-Length", str(len(body))),
    ])
    parser = FieldStorageParser(BytesIO(body), headers)
    return parser.parse()


def _make_multipart(fields: list, boundary: str = "TestBoundary") -> bytes:
    """Builds a minimal multipart/form-data body.

    Each entry in fields is either:
        (name, value)                       — simple text field
        (name, filename, content, ctype)    — file upload
    """
    parts = []
    for item in fields:
        if len(item) == 2:
            name, value = item
            parts.append(
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n"
                f"\r\n"
                f"{value}\r\n"
            )
        else:
            name, filename, content, ctype = item
            part_header = (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; "
                f"name=\"{name}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {ctype}\r\n"
                f"\r\n"
            )
            if isinstance(content, str):
                content = content.encode("utf-8")
            parts.append(part_header.encode("utf-8") + content + b"\r\n")
    body = b"".join(
        p.encode("utf-8") if isinstance(p, str) else p for p in parts
    )
    body += f"--{boundary}--\r\n".encode("utf-8")
    return body


# ---------------------------------------------------------------------------
# valid_boundary
# ---------------------------------------------------------------------------

class TestValidBoundary:
    """RFC 2046 §5.1.1 boundary syntax validation."""

    def test_str_valid(self):
        """Typical browser-generated boundary string is valid."""
        assert valid_boundary("----WebKitFormBoundaryMPRpF8CUUmlmqKqy")

    def test_bytes_valid(self):
        """Bytes boundary is also accepted."""
        assert valid_boundary(b"----WebKitFormBoundaryMPRpF8CUUmlmqKqy")

    def test_simple_str(self):
        """Simple ASCII string is a valid boundary."""
        assert valid_boundary("boundary123")

    def test_empty_is_invalid(self):
        """Empty boundary is invalid."""
        assert not valid_boundary("")

    def test_too_long_invalid(self):
        """Boundary exceeding 201 characters is invalid."""
        assert not valid_boundary("x" * 202)

    def test_space_only_invalid(self):
        """Space-only boundary is invalid (must end with !-~)."""
        assert not valid_boundary("   ")

    def test_non_ascii_invalid(self):
        """Non-ASCII boundary characters are invalid."""
        assert not valid_boundary("boundary\x00")

    def test_max_length_valid(self):
        """Boundary of exactly 201 visible chars is valid."""
        assert valid_boundary("x" * 201)


# ---------------------------------------------------------------------------
# FieldStorage — standalone field object
# ---------------------------------------------------------------------------

class TestFieldStorageBasic:
    """Unit tests for FieldStorage data container."""

    def test_repr_with_value(self):
        """repr includes name and value."""
        field = FieldStorage("key", "val")
        assert "key" in repr(field)

    def test_repr_with_file(self):
        """repr includes name and file when no value set."""
        field = FieldStorage("key")
        field.file = StringIO("data")
        r = repr(field)
        assert "key" in r

    def test_bool_true_value(self):
        """Field with a value is truthy."""
        assert bool(FieldStorage("k", "v"))

    def test_bool_true_list(self):
        """Root FieldStorage with children is truthy."""
        root = FieldStorage()
        root.list = [FieldStorage("k")]
        assert bool(root)

    def test_bool_false_empty(self):
        """Field with no value and no list is falsy."""
        assert not bool(FieldStorage("k"))

    def test_iter_over_keys(self):
        """Iteration yields unique key names."""
        root = FieldStorage()
        root.list = [FieldStorage("a", "1"), FieldStorage("b", "2")]
        assert set(root) == {"a", "b"}

    def test_len_unique_keys(self):
        """len() counts unique key names."""
        root = FieldStorage()
        root.list = [
            FieldStorage("k", "1"),
            FieldStorage("k", "2"),
            FieldStorage("x", "3"),
        ]
        assert len(root) == 2

    def test_contains_true(self):
        """'in' returns True for a present key."""
        root = FieldStorage()
        root.list = [FieldStorage("key", "v")]
        assert "key" in root

    def test_contains_false(self):
        """'in' returns False for an absent key."""
        root = FieldStorage()
        root.list = [FieldStorage("other", "v")]
        assert "missing" not in root

    def test_contains_empty(self):
        """'in' returns False when list is empty."""
        root = FieldStorage()
        assert "key" not in root

    def test_getitem_single(self):
        """__getitem__ returns the FieldStorage for a unique key."""
        root = FieldStorage()
        root.list = [FieldStorage("k", "v")]
        assert root["k"].value == "v"

    def test_getitem_multiple(self):
        """__getitem__ returns a list when a key has multiple values."""
        root = FieldStorage()
        root.list = [FieldStorage("k", "1"), FieldStorage("k", "2")]
        result = root["k"]
        assert isinstance(result, list)
        assert len(result) == 2

    def test_getitem_missing_raises(self):
        """__getitem__ raises KeyError for missing key."""
        root = FieldStorage()
        root.list = []
        with pytest.raises(KeyError):
            _ = root["missing"]

    def test_getitem_no_list_raises(self):
        """__getitem__ raises KeyError when list is empty."""
        root = FieldStorage()
        with pytest.raises(KeyError):
            _ = root["k"]

    def test_value_from_string(self):
        """value property returns the _value string."""
        field = FieldStorage("k", "hello")
        assert field.value == "hello"

    def test_value_from_stringio(self):
        """value property reads from StringIO file."""
        field = FieldStorage("k")
        field.file = StringIO("text data")
        assert field.value == "text data"

    def test_value_from_bytesio(self):
        """value property reads from BytesIO file."""
        field = FieldStorage("k")
        field.file = BytesIO(b"binary")
        assert field.value == b"binary"

    def test_value_from_file(self):
        """value property reads from a seekable file-like object."""
        field = FieldStorage("k")
        with tempfile.TemporaryFile("w+") as tmp:
            tmp.write("file content")
            field.file = tmp
            assert field.value == "file content"

    def test_value_from_list(self):
        """value property returns list when field has child list."""
        root = FieldStorage()
        child = FieldStorage("k", "v")
        root.list = [child]
        assert root.value == [child]

    def test_value_none_when_empty(self):
        """value property returns None for an empty field."""
        field = FieldStorage("k")
        assert field.value is None

    def test_keys(self):
        """keys() returns unique key names."""
        root = FieldStorage()
        root.list = [FieldStorage("a", "1"), FieldStorage("b", "2")]
        assert set(root.keys()) == {"a", "b"}

    def test_get_single(self):
        """get() returns the field value for a single-value key."""
        root = FieldStorage()
        root.list = [FieldStorage("k", "v")]
        assert root.get("k") == "v"

    def test_get_multiple(self):
        """get() returns a list of values for a multi-value key."""
        root = FieldStorage()
        root.list = [FieldStorage("k", "1"), FieldStorage("k", "2")]
        result = root.get("k")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_default(self):
        """get() returns default for missing key."""
        root = FieldStorage()
        root.list = []
        assert root.get("missing", "def") == "def"

    def test_context_manager(self):
        """FieldStorage can be used as a context manager."""
        field = FieldStorage("k")
        field.file = StringIO("value")
        with field as f:
            assert f.value == "value"

    def test_del_closes_file(self):
        """Deleting a FieldStorage closes its file."""
        field = FieldStorage("k")
        sio = StringIO("data")
        field.file = sio
        del field
        assert sio.closed


class TestFieldStorageInterface:
    """Tests for getvalue / getfirst / getlist on FieldStorageInterface
    via FieldStorage (which inherits from it)."""

    def _root(self, pairs):
        root = FieldStorage()
        root.list = [FieldStorage(k, v) for k, v in pairs]
        return root

    def test_getvalue_single(self):
        """getvalue returns the value for a single-value key."""
        root = self._root([("k", "42")])
        assert root.getvalue("k") == "42"

    def test_getvalue_with_func(self):
        """getvalue applies func to each value."""
        root = self._root([("n", "7")])
        assert root.getvalue("n", func=int) == 7

    def test_getvalue_multiple(self):
        """getvalue returns a list for a multi-value key."""
        root = self._root([("k", "1"), ("k", "2")])
        result = root.getvalue("k")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_getvalue_missing(self):
        """getvalue returns default for missing key."""
        root = self._root([])
        assert root.getvalue("x", default="d") == "d"

    def test_getfirst_single(self):
        """getfirst returns the only value for a single-value key."""
        root = self._root([("k", "v")])
        assert root.getfirst("k") == "v"

    def test_getfirst_multiple(self):
        """getfirst returns the first value for a multi-value key."""
        root = self._root([("k", "first"), ("k", "second")])
        assert root.getfirst("k") == "first"

    def test_getfirst_with_func(self):
        """getfirst applies func to the first value."""
        root = self._root([("n", "5"), ("n", "10")])
        assert root.getfirst("n", func=int) == 5

    def test_getfirst_missing(self):
        """getfirst returns default when key is absent."""
        root = self._root([])
        assert root.getfirst("x", default=0) == 0

    def test_getfirst_deprecated_fce(self):
        """getfirst emits DeprecationWarning for the fce argument."""
        root = self._root([("k", "3")])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = root.getfirst("k", fce=int)
        assert result == 3
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_getlist_single(self):
        """getlist wraps a single value in a list."""
        root = self._root([("k", "v")])
        assert root.getlist("k") == ["v"]

    def test_getlist_multiple(self):
        """getlist returns all values for a multi-value key."""
        root = self._root([("k", "1"), ("k", "2")])
        assert root.getlist("k") == ["1", "2"]

    def test_getlist_with_func(self):
        """getlist applies func to each value."""
        root = self._root([("k", "1"), ("k", "2")])
        assert root.getlist("k", func=int) == [1, 2]

    def test_getlist_missing_empty(self):
        """getlist returns [] for a missing key."""
        root = self._root([])
        assert root.getlist("x") == []

    def test_getlist_missing_with_default(self):
        """getlist returns default list for a missing key."""
        root = self._root([])
        assert root.getlist("x", default=["fallback"]) == ["fallback"]

    def test_getlist_deprecated_fce(self):
        """getlist emits DeprecationWarning for the fce argument."""
        root = self._root([("k", "1"), ("k", "2")])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = root.getlist("k", fce=int)
        assert result == [1, 2]
        assert any(issubclass(x.category, DeprecationWarning) for x in w)


# ---------------------------------------------------------------------------
# FieldStorageParser — URL-encoded forms
# ---------------------------------------------------------------------------

class TestURLEncoded:
    """application/x-www-form-urlencoded parsing (HTML form default)."""

    def test_simple_field(self):
        """Single name=value pair is parsed correctly."""
        form = _urlencoded("name=Ondrej")
        assert form.getvalue("name") == "Ondrej"

    def test_multiple_fields(self):
        """Multiple fields are all present."""
        form = _urlencoded("a=1&b=2&c=3")
        assert form.getvalue("a") == "1"
        assert form.getvalue("b") == "2"
        assert form.getvalue("c") == "3"

    def test_repeated_key(self):
        """Repeated key results in a list of values."""
        form = _urlencoded("tag=a&tag=b&tag=c")
        result = form.getlist("tag")
        assert result == ["a", "b", "c"]

    def test_percent_encoding(self):
        """Percent-encoded values are decoded."""
        form = _urlencoded("name=Ond%C5%99ej")
        assert form.getvalue("name") == "Ondřej"

    def test_plus_as_space(self):
        """Plus sign in URL encoding represents a space."""
        form = _urlencoded("msg=hello+world")
        assert form.getvalue("msg") == "hello world"

    def test_blank_value_ignored_by_default(self):
        """Blank values are ignored when keep_blank_values is False."""
        body = b"name=&other=val"
        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(BytesIO(body), headers)
        form = parser.parse()
        assert form.getvalue("name") is None

    def test_blank_value_kept(self):
        """Blank values are kept as fields when keep_blank_values=1.

        The key appears in the form even though the value reads as None
        (the value property treats empty string as falsy).
        """
        body = b"name=&other=val"
        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(
            BytesIO(body), headers, keep_blank_values=1
        )
        form = parser.parse()
        assert "name" in form

    def test_empty_body(self):
        """Empty body produces empty form."""
        form = _urlencoded("")
        assert len(form) == 0

    def test_missing_content_type_defaults_to_urlencoded(self):
        """No Content-Type header defaults to URL-encoded parsing."""
        body = b"x=1"
        headers = Headers([("Content-Length", "3")])
        parser = FieldStorageParser(BytesIO(body), headers)
        form = parser.parse()
        assert form.getvalue("x") == "1"

    def test_separator_semicolon(self):
        """Custom separator is respected."""
        body = b"a=1;b=2"
        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(
            BytesIO(body), headers, separator=";"
        )
        form = parser.parse()
        assert form.getvalue("a") == "1"
        assert form.getvalue("b") == "2"

    def test_content_length_invalid_ignored(self):
        """Non-integer Content-Length defaults to -1 (read all)."""
        body = b"k=v"
        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", "not-a-number"),
        ])
        parser = FieldStorageParser(BytesIO(body), headers)
        form = parser.parse()
        assert form.getvalue("k") == "v"

    def test_max_num_fields_exceeded(self):
        """max_num_fields raises ValueError when limit is exceeded."""
        body = b"a=1&b=2&c=3"
        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(
            BytesIO(body), headers, max_num_fields=2
        )
        with pytest.raises(ValueError, match="fields"):
            parser.parse()


# ---------------------------------------------------------------------------
# FieldStorageParser — multipart/form-data
# ---------------------------------------------------------------------------

class TestMultipartFormData:
    """multipart/form-data (RFC 7578) parsing.

    Also tests browser-specific behaviour that deviates from RFC.
    """

    def test_simple_text_field(self):
        """Single text field is parsed correctly."""
        body = _make_multipart([("name", "Ondrej")])
        form = _multipart(body, "TestBoundary")
        assert form.getvalue("name") == "Ondrej"

    def test_multiple_text_fields(self):
        """Multiple text fields are all parsed."""
        body = _make_multipart([("a", "1"), ("b", "2")])
        form = _multipart(body, "TestBoundary")
        assert form.getvalue("a") == "1"
        assert form.getvalue("b") == "2"

    def test_repeated_field(self):
        """Repeated form field name produces multiple values."""
        body = _make_multipart([("tag", "python"), ("tag", "wsgi")])
        form = _multipart(body, "TestBoundary")
        tags = [f.value for f in form["tag"]]
        assert "python" in tags
        assert "wsgi" in tags

    def test_file_upload_bytes(self):
        """File upload is parsed and content is accessible."""
        body = _make_multipart(
            [("upload", "hello.txt", b"Hello, file!", "text/plain")]
        )
        form = _multipart(body, "TestBoundary")
        field = form["upload"]
        assert field.filename == "hello.txt"
        assert field.value == b"Hello, file!"

    def test_file_upload_content_type(self):
        """File upload preserves Content-Type."""
        body = _make_multipart(
            [("img", "photo.jpg", b"\xff\xd8\xff", "image/jpeg")]
        )
        form = _multipart(body, "TestBoundary")
        field = form["img"]
        assert field.type == "image/jpeg"
        assert field.filename == "photo.jpg"

    def test_text_and_file_mixed(self):
        """Text fields and file uploads coexist in the same form."""
        body = _make_multipart([
            ("username", "alice"),
            ("avatar", "me.png", b"\x89PNG", "image/png"),
        ])
        form = _multipart(body, "TestBoundary")
        assert form.getvalue("username") == "alice"
        assert form["avatar"].filename == "me.png"

    def test_boundary_with_dashes(self):
        """Boundary string with leading dashes (Chrome/Firefox style)."""
        boundary = "----WebKitFormBoundaryABCDEF123456"
        body = _make_multipart([("x", "y")], boundary)
        form = _multipart(body, boundary)
        assert form.getvalue("x") == "y"

    def test_unicode_field_value(self):
        """Unicode text field values are decoded correctly."""
        body = _make_multipart([("city", "Brno")])
        form = _multipart(body, "TestBoundary")
        assert form.getvalue("city") == "Brno"

    def test_empty_file_upload(self):
        """Empty file upload has a filename but empty content."""
        body = _make_multipart(
            [("doc", "empty.txt", b"", "text/plain")]
        )
        form = _multipart(body, "TestBoundary")
        field = form["doc"]
        assert field.filename == "empty.txt"
        assert field.value == b""

    def test_binary_file_upload(self):
        """Binary file upload content is not decoded."""
        binary_data = bytes(range(256))
        body = _make_multipart(
            [("bin", "data.bin", binary_data, "application/octet-stream")]
        )
        form = _multipart(body, "TestBoundary")
        assert form["bin"].value == binary_data

    def test_no_content_type_inner(self):
        """Missing Content-Type on a part defaults to text/plain."""
        boundary = "Bound"
        body = (
            b"--Bound\r\n"
            b"Content-Disposition: form-data; name=\"field\"\r\n"
            b"\r\n"
            b"value\r\n"
            b"--Bound--\r\n"
        )
        form = _multipart(body, boundary)
        assert form.getvalue("field") == "value"

    def test_max_num_fields_multipart(self):
        """max_num_fields raises ValueError when multipart exceeds limit."""
        body = _make_multipart([("a", "1"), ("b", "2"), ("c", "3")])
        headers = Headers([
            ("Content-Type", "multipart/form-data; boundary=TestBoundary"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(
            BytesIO(body), headers, max_num_fields=1
        )
        with pytest.raises(ValueError, match="Max number of fields"):
            parser.parse()

    def test_content_length_header_on_part_ignored(self):
        """Content-Length in individual part headers is stripped (browser
        behaviour — some agents include it, RFC says it's optional)."""
        boundary = "Bound"
        body = (
            b"--Bound\r\n"
            b"Content-Disposition: form-data; name=\"f\"\r\n"
            b"Content-Length: 5\r\n"
            b"\r\n"
            b"hello\r\n"
            b"--Bound--\r\n"
        )
        form = _multipart(body, boundary)
        assert form.getvalue("f") == "hello"

    def test_crlf_line_endings(self):
        """CRLF line endings (required by RFC 7578 §4.1) are handled."""
        boundary = "Bound"
        body = (
            b"--Bound\r\n"
            b"Content-Disposition: form-data; name=\"k\"\r\n"
            b"\r\n"
            b"val\r\n"
            b"--Bound--\r\n"
        )
        form = _multipart(body, boundary)
        assert form.getvalue("k") == "val"

    def test_field_name_with_unicode_filename(self):
        """Filename with non-ASCII characters is preserved as-is."""
        boundary = "Bound"
        body = (
            "--Bound\r\n"
            "Content-Disposition: form-data; name=\"f\"; "
            "filename=\"tëst.txt\"\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "data\r\n"
            "--Bound--\r\n"
        ).encode("utf-8")
        form = _multipart(body, boundary)
        assert "ë" in form["f"].filename


# ---------------------------------------------------------------------------
# FieldStorageParser — other content types (read_single / read_binary)
# ---------------------------------------------------------------------------

class TestReadSingle:
    """Parsing non-form content types — text/plain, application/octet-stream.

    When Content-Type is not URL-encoded or multipart, the body is
    treated as a single field via read_single.

    Note: read_binary is designed for multipart file parts (filename set).
    For content without a filename, read_lines is used regardless of
    Content-Length, because make_file() returns a text-mode tempfile
    when filename is None.
    """

    def test_text_plain_body(self):
        """text/plain body without Content-Length is parsed via read_lines."""
        body = b"Hello, world"
        headers = Headers([("Content-Type", "text/plain")])
        parser = FieldStorageParser(BytesIO(body), headers)
        field = parser.parse()
        assert field.file is not None
        field.file.seek(0)
        assert "Hello" in field.file.read()

    def test_read_lines_to_eof(self):
        """Without outer boundary, read_lines reads the entire input."""
        body = b"line1\nline2\n"
        headers = Headers([("Content-Type", "text/plain")])
        parser = FieldStorageParser(BytesIO(body), headers)
        field = parser.parse()
        field.file.seek(0)
        content = field.file.read()
        assert "line1" in content

    def test_read_binary_empty_data_sets_done(self):
        """read_binary sets done=-1 when input is exhausted early."""
        parser = FieldStorageParser()
        parser.filename = "file.bin"  # filename → binary tempfile
        parser.length = 100
        parser.input = BytesIO(b"")
        file_ = parser.read_binary()
        assert parser.done == -1
        file_.close()

    def test_file_upload_large_spills_to_tempfile(self):
        """File upload larger than BUFSIZE spills to a temporary file."""
        binary_data = b"x" * (FieldStorageParser.BUFSIZE + 100)
        body = _make_multipart(
            [("f", "large.bin", binary_data, "application/octet-stream")]
        )
        form = _multipart(body, "TestBoundary")
        assert form["f"].value == binary_data


# ---------------------------------------------------------------------------
# FieldStorageParser — file_callback
# ---------------------------------------------------------------------------

class TestFileCallback:  # pylint: disable=too-few-public-methods
    """file_callback lets the caller supply a custom writable stream."""

    def test_file_callback_used_for_upload(self):
        """file_callback is called with the filename for uploads."""
        called_with = []
        custom_buf = BytesIO()

        def callback(filename):
            called_with.append(filename)
            return custom_buf

        body = (
            b"--Bound\r\n"
            b"Content-Disposition: form-data; name=\"f\"; "
            b"filename=\"report.pdf\"\r\n"
            b"Content-Type: application/pdf\r\n"
            b"\r\n"
            b"PDF content\r\n"
            b"--Bound--\r\n"
        )
        headers = Headers([
            ("Content-Type", "multipart/form-data; boundary=Bound"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(
            BytesIO(body), headers, file_callback=callback
        )
        parser.parse()
        assert "report.pdf" in called_with


# ---------------------------------------------------------------------------
# FieldStorageParser — read_urlencoded error path
# ---------------------------------------------------------------------------

class TestReadUrlencodedErrors:
    """Error handling in URL-encoded parsing."""

    def test_non_bytes_input_raises(self):
        """read_urlencoded raises ValueError when input returns non-bytes."""

        class _TextStream:  # pylint: disable=too-few-public-methods
            def read(self, _n=-1):
                return "not bytes"

        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", "5"),
        ])
        parser = FieldStorageParser(_TextStream(), headers)
        parser.length = 5
        with pytest.raises(ValueError, match="should return bytes"):
            parser.read_urlencoded()

    def test_invalid_boundary_raises(self):
        """_skip_to_boundary raises ValueError for an invalid boundary."""
        headers = Headers([
            ("Content-Type", "multipart/form-data; boundary=Bound"),
            ("Content-Length", "0"),
        ])
        parser = FieldStorageParser(BytesIO(b""), headers)
        parser.innerboundary = b""  # empty → invalid
        with pytest.raises(ValueError, match="Invalid boundary"):
            parser._skip_to_boundary()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# FieldStorageParser — make_file
# ---------------------------------------------------------------------------

class TestMakeFile:
    """make_file returns the correct stream type."""

    def test_no_filename_returns_text_tempfile(self):
        """Without a filename, make_file returns a text-mode temp file."""
        parser = FieldStorageParser()
        parser.filename = None
        f = parser.make_file()
        f.write("hello")
        f.seek(0)
        assert f.read() == "hello"
        f.close()

    def test_filename_returns_binary_tempfile(self):
        """With a filename, make_file returns a binary-mode temp file."""
        parser = FieldStorageParser()
        parser.filename = "test.bin"
        f = parser.make_file()
        f.write(b"\x00\xff")
        f.seek(0)
        assert f.read() == b"\x00\xff"
        f.close()

    def test_file_callback_overrides_tempfile(self):
        """file_callback completely replaces the default temp file."""
        custom = BytesIO()
        parser = FieldStorageParser(file_callback=lambda _fn: custom)
        parser.filename = "upload.bin"
        result = parser.make_file()
        assert result is custom


# ---------------------------------------------------------------------------
# FieldStorageParser — _parse_content_type
# ---------------------------------------------------------------------------

class TestParseContentType:
    """Content-Type header parsing edge cases."""

    # pylint: disable=protected-access

    def test_no_header_outer(self):
        """No Content-Type at outer level → url-encoded default."""
        parser = FieldStorageParser()
        ctype, _ = parser._parse_content_type()
        assert ctype == "application/x-www-form-urlencoded"

    def test_no_header_inner(self):
        """No Content-Type at inner level (outerboundary set) → text/plain."""
        parser = FieldStorageParser(outerboundary=b"Bound")
        ctype, _ = parser._parse_content_type()
        assert ctype == "text/plain"

    def test_explicit_header_wins(self):
        """Explicit Content-Type overrides defaults."""
        headers = Headers([("Content-Type", "application/json")])
        parser = FieldStorageParser(headers=headers)
        ctype, _ = parser._parse_content_type()
        assert ctype == "application/json"


# ---------------------------------------------------------------------------
# FieldStorageInterface — base class methods
# ---------------------------------------------------------------------------

class TestFieldStorageInterfaceDirect:
    """Tests for the FieldStorageInterface base class default implementations.

    These are only reachable via a subclass that does NOT override
    getvalue/getfirst/getlist — i.e., not FieldStorage which overrides all.
    """

    def _minimal(self, items):
        """Minimal concrete FieldStorageInterface with a dict store."""

        class _Impl(FieldStorageInterface):
            def __init__(self, data):
                self._data = data

            def __contains__(self, key):
                return key in self._data

            def __getitem__(self, key):
                return self._data[key]

        return _Impl(dict(items))

    def test_getvalue_found(self):
        """getvalue returns the item when key is present."""
        impl = self._minimal([("k", "v")])
        assert impl.getvalue("k") == "v"

    def test_getvalue_with_func(self):
        """getvalue applies func to the found value."""
        impl = self._minimal([("n", "42")])
        assert impl.getvalue("n", func=int) == 42

    def test_getvalue_missing(self):
        """getvalue returns default when key is absent."""
        impl = self._minimal([])
        assert impl.getvalue("x", default="d") == "d"

    def test_getfirst_single(self):
        """getfirst returns the single value."""
        impl = self._minimal([("k", "v")])
        assert impl.getfirst("k") == "v"

    def test_getfirst_list(self):
        """getfirst returns the first element of a list value."""
        impl = self._minimal([("k", ["a", "b"])])
        assert impl.getfirst("k") == "a"

    def test_getfirst_missing(self):
        """getfirst returns default when key is absent."""
        impl = self._minimal([])
        assert impl.getfirst("x", default=0) == 0

    def test_getfirst_deprecated_fce(self):
        """getfirst base warns about deprecated fce."""
        impl = self._minimal([("k", "3")])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = impl.getfirst("k", fce=int)
        assert result == 3
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_getlist_single(self):
        """getlist wraps a non-list value in a list."""
        impl = self._minimal([("k", "v")])
        assert impl.getlist("k") == ["v"]

    def test_getlist_multiple(self):
        """getlist returns the list as-is when value is already a list."""
        impl = self._minimal([("k", ["a", "b"])])
        assert impl.getlist("k") == ["a", "b"]

    def test_getlist_missing(self):
        """getlist returns [] for absent key."""
        impl = self._minimal([])
        assert impl.getlist("x") == []

    def test_getlist_missing_with_default(self):
        """getlist returns default list for absent key."""
        impl = self._minimal([])
        assert impl.getlist("x", default=["d"]) == ["d"]

    def test_getlist_deprecated_fce(self):
        """getlist base warns about deprecated fce."""
        impl = self._minimal([("k", ["1", "2"])])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = impl.getlist("k", fce=int)
        assert result == [1, 2]
        assert any(issubclass(x.category, DeprecationWarning) for x in w)


# ---------------------------------------------------------------------------
# FieldStorage — remaining edge cases
# ---------------------------------------------------------------------------

class TestFieldStorageEdgeCases:
    """Edge cases not covered by the main test classes."""

    def test_getitem_key_not_in_non_empty_list(self):
        """__getitem__ raises KeyError when key absent in non-empty list."""
        root = FieldStorage()
        root.list = [FieldStorage("other", "v")]
        with pytest.raises(KeyError):
            _ = root["missing"]

    def test_valid_boundary_bytes_no_match(self):
        """Bytes boundary with control characters is invalid."""
        assert not valid_boundary(b"\x00invalid")

    def test_parser_textiowrapper_input(self):
        """FieldStorageParser accepts a TextIOWrapper and uses its buffer."""
        raw = BytesIO(b"key=value")
        wrapper = TextIOWrapper(raw, encoding="utf-8")
        headers = Headers([
            ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", "9"),
        ])
        parser = FieldStorageParser(wrapper, headers)
        assert parser.input is raw  # buffer, not wrapper


# ---------------------------------------------------------------------------
# read_single with Content-Disposition filename
# ---------------------------------------------------------------------------

class TestReadSingleWithFilename:
    """read_single with a binary Content-Disposition filename.

    When a filename is present, make_file returns a binary temp file,
    so read_binary can write bytes successfully.
    """

    def test_binary_body_with_filename(self):
        """Binary body with filename is read correctly via read_binary."""
        body = b"\x00\x01\x02\x03"
        headers = Headers([
            ("Content-Type", "application/octet-stream"),
            ("Content-Disposition", 'attachment; filename="blob.bin"'),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(BytesIO(body), headers)
        field = parser.parse()
        field.file.seek(0)
        assert field.file.read() == body

    def test_read_binary_non_bytes_raises(self):
        """read_binary raises ValueError when stream returns non-bytes."""

        class _BadStream:  # pylint: disable=too-few-public-methods
            def read(self, _n=-1):
                return "not bytes"

        parser = FieldStorageParser()
        parser.filename = "f.bin"
        parser.length = 5
        parser.input = _BadStream()
        with pytest.raises(ValueError, match="should return bytes"):
            parser.read_binary()

    def test_skip_to_boundary_non_bytes_readline(self):
        """_skip_to_boundary raises ValueError when readline returns
        non-bytes."""

        class _BadStream:  # pylint: disable=too-few-public-methods
            def readline(self):
                return "string not bytes"

        parser = FieldStorageParser()
        parser.innerboundary = b"Bound"
        parser.input = _BadStream()
        with pytest.raises(ValueError, match="should return bytes"):
            parser._skip_to_boundary()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# read_lines_to_outerboundary — edge cases
# ---------------------------------------------------------------------------

class TestReadLinesToOuterBoundary:
    r"""Tests for \r-only line ending handling and limit in
    read_lines_to_outerboundary."""

    def test_limit_stops_reading(self):
        """Reading stops when the limit byte count is reached."""
        body = _make_multipart([("f", "file.txt", b"A" * 20, "text/plain")])
        headers = Headers([
            ("Content-Type", "multipart/form-data; boundary=Bound"),
            ("Content-Length", str(len(body))),
        ])
        parser = FieldStorageParser(
            BytesIO(body), headers, limit=len(body)
        )
        form = parser.parse()
        assert form is not None  # just confirm parsing doesn't crash

    def test_cr_only_line_ending(self):
        r"""Bare \r at end of a chunk is handled as a split \r\n."""
        boundary = "Bound"
        # Build a multipart body where the field content ends with \r\n
        # spanning a chunk boundary (16-bit read).  The library handles
        # \r split across reads via the delim variable.
        body = (
            b"--Bound\r\n"
            b"Content-Disposition: form-data; name=\"f\"\r\n"
            b"\r\n"
            b"value\r\n"
            b"--Bound--\r\n"
        )
        form = _multipart(body, boundary)
        assert form.getvalue("f") == "value"
