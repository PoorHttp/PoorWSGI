"""Unit tests for poorwsgi/headers.py module-level functions and Headers."""
from datetime import datetime, timezone

from pytest import raises

from poorwsgi.headers import (
    ContentRange,
    Headers,
    datetime_to_http,
    http_to_datetime,
    http_to_time,
    parse_header,
    parse_negotiation,
    parse_range,
    render_negotiation,
    time_to_http,
)

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=too-few-public-methods

EPOCH = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
EPOCH_HTTP = "Thu, 01 Jan 1970 00:00:00 GMT"


class TestParseHeader:
    """Tests for parse_header()."""

    def test_simple(self):
        key, params = parse_header("text/html")
        assert key == "text/html"
        assert not params

    def test_with_param(self):
        key, params = parse_header("text/html; charset=utf-8")
        assert key == "text/html"
        assert params == {"charset": "utf-8"}

    def test_quoted_value(self):
        key, params = parse_header('attachment; filename="hello world.txt"')
        assert key == "attachment"
        assert params["filename"] == "hello world.txt"

    def test_quoted_semicolon_in_value(self):
        """Semicolon inside a quoted string must not split the parameter."""
        key, params = parse_header('form-data; name="a;b"')
        assert key == "form-data"
        assert params["name"] == "a;b"


class TestParseNegotiation:
    """Tests for parse_negotiation()."""

    def test_single_no_quality(self):
        assert parse_negotiation("gzip") == [("gzip", 1.0)]

    def test_multiple_with_quality(self):
        result = parse_negotiation("gzip;q=1.0, identity;q=0.5, *;q=0")
        assert result == [("gzip", 1.0), ("identity", 0.5), ("*", 0.0)]

    def test_param_before_quality(self):
        result = parse_negotiation(
            "text/html;level=1, text/html;level=2;q=0.5")
        assert result == [("text/html;level=1", 1.0),
                          ("text/html;level=2", 0.5)]

    def test_bad_quality_falls_back_to_1(self):
        """Non-numeric quality value must fall back to 1.0."""
        result = parse_negotiation("br;q=bad")
        assert result == [("br", 1.0)]


class TestRenderNegotiation:
    """Tests for render_negotiation()."""

    def test_with_quality(self):
        assert render_negotiation([("gzip", 1.0), ("*", 0)]) == \
            "gzip;q=1.0, *;q=0"

    def test_without_quality(self):
        assert render_negotiation([("gzip",)]) == "gzip"


class TestParseRange:
    """Tests for parse_range()."""

    def test_simple(self):
        assert parse_range("bytes=0-499") == {"bytes": [(0, 499)]}

    def test_suffix_range(self):
        assert parse_range("bytes=-500") == {"bytes": [(None, 500)]}

    def test_open_ended(self):
        assert parse_range("bytes=9500-") == {"bytes": [(9500, None)]}

    def test_multi_range(self):
        assert parse_range("chunks=500-600,601-999") == \
            {"chunks": [(500, 600), (601, 999)]}

    def test_invalid_no_equals(self):
        assert not parse_range("invalid")

    def test_invalid_values(self):
        result = parse_range("invalid=a-b")
        assert result == {"invalid": []}

    def test_empty_pair_skipped(self):
        """A '-' with no numbers on either side must be silently skipped."""
        result = parse_range("bytes=0-1,-")
        assert result == {"bytes": [(0, 1)]}


class TestDatetimeFunctions:
    """Tests for datetime_to_http, time_to_http, http_to_datetime,
    http_to_time."""

    def test_datetime_to_http(self):
        assert datetime_to_http(EPOCH) == EPOCH_HTTP

    def test_time_to_http_with_value(self):
        assert time_to_http(0) == EPOCH_HTTP

    def test_time_to_http_without_value(self):
        result = time_to_http()
        assert result.endswith(" GMT")

    def test_http_to_datetime(self):
        assert http_to_datetime(EPOCH_HTTP) == EPOCH

    def test_http_to_time(self):
        assert http_to_time(EPOCH_HTTP) == 0


class TestContentRange:
    """Tests for ContentRange."""

    def test_without_full(self):
        assert str(ContentRange(1, 2)) == "bytes 1-2/*"

    def test_with_full(self):
        assert str(ContentRange(1, 2, 10)) == "bytes 1-2/10"

    def test_custom_units(self):
        assert str(ContentRange(2, 5, units="lines")) == "lines 2-5/*"


class TestHeadersMethods:
    """Tests for Headers methods not covered by test_header.py."""

    def test_repr(self):
        headers = Headers([("X-Test", "value")])
        assert "X-Test" in repr(headers)

    def test_names_and_keys(self):
        headers = Headers([("X-A", "1"), ("X-B", "2")])
        assert headers.names() == ("X-A", "X-B")
        assert headers.keys() == headers.names()

    def test_values(self):
        headers = Headers([("X-A", "1"), ("X-B", "2")])
        assert headers.values() == ("1", "2")

    def test_get_all_multiple(self):
        headers = Headers([("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")])
        assert headers.get_all("Set-Cookie") == ("a=1", "b=2")

    def test_get_all_missing(self):
        assert not Headers().get_all("X-Missing")

    def test_delitem(self):
        headers = Headers([("X-Test", "v")])
        del headers["X-Test"]
        assert "X-Test" not in headers

    def test_setitem_overwrites(self):
        headers = Headers([("X-Test", "old")])
        headers["X-Test"] = "new"
        assert headers["X-Test"] == "new"
        assert len(headers.get_all("X-Test")) == 1

    def test_setdefault_missing(self):
        headers = Headers()
        result = headers.setdefault("X-Test", "default")
        assert result == "default"
        assert headers["X-Test"] == "default"

    def test_setdefault_existing(self):
        headers = Headers([("X-Test", "original")])
        result = headers.setdefault("X-Test", "other")
        assert result == "original"

    def test_add_duplicate_raises(self):
        headers = Headers([("X-Test", "v")])
        with raises(KeyError):
            headers.add("X-Test", "v2")

    def test_add_set_cookie_allows_duplicate(self):
        headers = Headers()
        headers.add("Set-Cookie", "a=1")
        headers.add("Set-Cookie", "b=2")
        assert len(headers.get_all("Set-Cookie")) == 2

    def test_add_header_none_kwarg(self):
        """Kwarg with value=None adds a bare flag (no '=value' suffix)."""
        headers = Headers()
        headers.add_header("Cache-Control", "no-cache", no_store=None)
        assert headers["Cache-Control"] == "no-cache; no-store"

    def test_strict_false_list(self):
        headers = Headers([("X-Raw", "value")], strict=False)
        assert headers["X-Raw"] == "value"

    def test_strict_false_dict(self):
        headers = Headers({"X-Raw": "value"}, strict=False)
        assert headers["X-Raw"] == "value"

    def test_iso88591_unicode_error(self):
        """Lone surrogate codepoints cannot be UTF-8 encoded and must raise
        ValueError."""
        with raises(ValueError, match="iso-8859-1"):
            Headers.iso88591("\ud800")  # lone surrogate

    def test_utf8_roundtrip(self):
        original = "café"
        iso = original.encode("utf-8").decode("iso-8859-1")
        assert Headers.utf8(iso) == original

    def test_utf8_already_utf8(self):
        """Bytes that cannot be decoded as UTF-8 (raw ISO-8859-1 high bytes)
        are returned as-is."""
        raw = "\x80"  # U+0080 → b'\x80' as ISO-8859-1, invalid as UTF-8
        assert Headers.utf8(raw) == raw

    def test_len(self):
        headers = Headers([("X-A", "1"), ("X-B", "2")])
        assert len(headers) == 2

    def test_iter(self):
        pairs = [("X-A", "1"), ("X-B", "2")]
        headers = Headers(pairs)
        assert list(headers) == pairs
