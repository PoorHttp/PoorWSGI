"""Tests for Response objects and their functionality."""

import re
import warnings
from datetime import datetime, timezone
from io import BufferedWriter, BytesIO, RawIOBase
from unittest.mock import patch

import pytest
from simplejson import load, loads

from poorwsgi.request import Headers
from poorwsgi.response import (
    BaseResponse,
    Declined,
    EmptyResponse,
    FileObjResponse,
    FileResponse,
    GeneratorResponse,
    HTTPException,
    IBytesIO,
    JSONGeneratorResponse,
    JSONResponse,
    NoContentResponse,
    NotModifiedResponse,
    PartialResponse,
    RedirectResponse,
    Response,
    ResponseError,
    StrGeneratorResponse,
    TextResponse,
    abort,
    make_response,
    redirect,
)
from poorwsgi.state import (
    DECLINED,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_PARTIAL_CONTENT,
)  # , HTTP_RANGE_NOT_SATISFIABLE

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use
# pylint: disable=too-many-lines


args = (
    ("<html></html>",),
    (b"<html></html>",),
    ("text", "text/plain"),
    (b"data", "application/octet-stream"),
    ("text", "text/plain", (("X-Header", "Value"),)),
    ("text", "text/plain", Headers((("X-Header", "Value"),))),
    ("text", "text/plain", Headers((("X-Header", "Value"),)), HTTP_NOT_FOUND),
)

kwargs = (
    {"data": "<html></html>"},
    {"data": "<html></html>"},
    {"content_type": "text/plain"},
    {"headers": (("X-Header", "Value"),)},
    {"status_code": HTTP_NOT_FOUND},
)


@pytest.fixture(params=args)
def response_args(request):
    return Response(*request.param)


@pytest.fixture(params=kwargs)
def response_kwargs(request):
    return Response(**request.param)


def write(data):
    assert isinstance(data, bytes)
    assert False


def start_response(status_code, headers):
    assert isinstance(status_code, str)
    assert isinstance(headers, list)
    return write


class TestReponse:
    """Basic tests for Response objects."""

    def test_args(self, response_args):
        """Tests Response initialization with positional arguments."""
        res = response_args(start_response)
        assert isinstance(res.read(), bytes)

    def test_kwargs(self, response_kwargs):
        """Tests Response initialization with keyword arguments."""
        res = response_kwargs(start_response)
        assert isinstance(res.read(), bytes)

    def test_once(self, response_args):
        """Tests that a Response object can only be used once."""
        response_args(start_response)
        with pytest.raises(RuntimeError):
            response_args(start_response)


class TestPartial:
    """Tests for Partial Response functionality."""

    def test_no_accept_range(self):
        """Tests that Accept-Ranges header is not set by default."""
        res = Response()
        assert res.headers.get("Accept-Ranges") is None

    def test_make_partial(self):
        """Tests the make_partial method with default units."""
        res = Response()
        res.make_partial()
        assert res.headers.get("Accept-Ranges") == "bytes"

    def test_make_partial_chunks(self):
        """Tests the make_partial method with 'chunks' units."""
        res = Response()
        res.make_partial(units="chunks")
        assert res.headers.get("Accept-Ranges") == "chunks"

    def test_cant_be_partial(self):
        """Tests that a non-HTTP_OK response cannot be partial."""
        res = Response(status_code=HTTP_NOT_FOUND)
        res.make_partial()
        assert res.headers.get("Accept-Ranges") is None

    def test_cant_be_partial_after(self):
        """Tests that partial content is cleared if status code changes after
        make_partial."""
        res = Response()
        res.make_partial([(0, 3)])
        res.status_code = HTTP_NOT_FOUND
        assert res.headers.get("Accept-Ranges") is None

    def test_partial_content_start(self):
        """Tests partial content response from the start of the content."""
        res = Response(b"0123456789")
        res.make_partial([(0, 4)])
        assert res(start_response).read() == b"01234"
        assert int(res.headers.get("Content-Length")) == 5
        assert res.headers.get("Content-Range") == "bytes 0-4/10"

    def test_partial_content_mid(self):
        """Tests partial content response from the middle of the content."""
        res = Response(b"0123456789")
        res.make_partial([(3, 6)])
        assert res(start_response).read() == b"3456"
        assert int(res.headers.get("Content-Length")) == 4
        assert res.headers.get("Content-Range") == "bytes 3-6/10"

    def test_partial_content_end(self):
        """Tests partial content response to the end of the content."""
        res = Response(b"0123456789")
        res.make_partial([(5, 9)])
        assert res(start_response).read() == b"56789"
        assert int(res.headers.get("Content-Length")) == 5
        assert res.headers.get("Content-Range") == "bytes 5-9/10"

    def test_partial_content_more(self):
        """Tests partial content response with a range exceeding content
        length."""
        res = Response(b"0123456789")
        res.make_partial([(8, 15)])
        assert res(start_response).read() == b"89"
        assert int(res.headers.get("Content-Length")) == 2
        assert res.headers.get("Content-Range") == "bytes 8-9/10"

    def test_partial_content_over(self):
        """Tests partial content response with a range entirely beyond content
        length."""
        res = Response(b"0123456789")
        res.make_partial([(10, 15)])
        with pytest.raises(HTTPException) as err:
            res(start_response)
        # assert isinstance(err.value.response, RangeNotSatisfiable)
        assert err.value.response.status_code == 416

    def test_partial_content_last(self):
        """Tests partial content response requesting the last N bytes."""
        res = Response(b"0123456789")
        res.make_partial([(None, 2)])
        assert res(start_response).read() == b"89"
        assert int(res.headers.get("Content-Length")) == 2
        assert res.headers.get("Content-Range") == "bytes 8-9/10"

    def test_partial_content_last_more(self):
        """Tests partial content response requesting more than available last N
        bytes."""
        res = Response(b"0123456789")
        res.make_partial([(None, 20)])
        assert res(start_response).read() == b"0123456789"
        assert int(res.headers.get("Content-Length")) == 10
        assert res.headers.get("Content-Range") == "bytes 0-9/10"

    def test_partial_content_from(self):
        """Tests partial content response from a specific byte to the end."""
        res = Response(b"0123456789")
        res.make_partial([(7, None)])
        assert res(start_response).read() == b"789"
        assert int(res.headers.get("Content-Length")) == 3
        assert res.headers.get("Content-Range") == "bytes 7-9/10"

    def test_partial_contents(self):
        """Tests partial content response with multiple ranges (only first is
        used)."""
        res = Response(b"0123456789")
        # Not supported now
        res.make_partial([(0, 2), (8, 9)])
        # Only first range was returned
        assert res(start_response).read() == b"012"
        assert int(res.headers.get("Content-Length")) == 3
        assert res.headers.get("Content-Range") == "bytes 0-2/10"

    def test_unknown_units(self):
        """Tests partial content response with unknown units, expecting full
        response."""
        res = Response(b"0123456789")
        res.make_partial([(2, 4)], "lines")
        assert res(start_response).read() == b"0123456789"
        assert "Content-Range" not in res.headers
        assert res.headers.get("Accept-Ranges") == "lines"


class TestPartialResponse:
    """Tests for the special PartialResponse class."""

    def test_response(self):
        """Tests basic PartialResponse with custom units."""
        res = PartialResponse(b"56789")
        res.make_range([(5, 9)], "chars")
        assert res(start_response).read() == b"56789"
        assert int(res.headers.get("Content-Length")) == 5
        assert res.headers.get("Content-Range") == "chars 5-9/*"

    def test_full(self):
        """Tests PartialResponse with full range information."""
        res = PartialResponse(b"56789")
        res.make_range([(5, 9)], "chars", 25)
        assert res(start_response).read() == b"56789"
        assert int(res.headers.get("Content-Length")) == 5
        assert res.headers.get("Content-Range") == "chars 5-9/25"

    def test_partial(self):
        """Tests make_partial method behavior in PartialResponse (should do
        nothing)."""
        res = PartialResponse(b"56789")
        res.make_partial([(5, 9)], "chars")
        assert "Accept-Range" not in res.headers
        assert "Content-Range" not in res.headers


class TestPartialGenerator:
    """Tests for Partial Response via generators."""

    def test_partial_known_length(self):
        """Tests partial response for generators with known content length from
        a start byte."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") for x in range(10)), content_length=10
        )
        res.make_partial([(7, None)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 3
        assert res.headers.get("Content-Range") == "bytes 7-9/10"
        assert b"".join(gen) == b"789"

    def test_partial_known_length_rewrite(self):
        """Tests partial response for generators with known content length and
        Content-Length header rewritten."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") for x in range(10)),
            content_length=10,
            headers={"Content-Length": "10"},
        )
        res.make_partial([(7, None)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 3
        assert res.headers.get("Content-Range") == "bytes 7-9/10"
        assert b"".join(gen) == b"789"

    def test_partial_known_length_blocks_start(self):
        """Tests partial response for generators with known content length and
        block reading from start."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") * 3 for x in range(10)), content_length=30
        )
        res.make_partial([(0, 6)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 7
        assert res.headers.get("Content-Range") == "bytes 0-6/30"
        assert b"".join(gen) == b"0001112"

    def test_partial_known_length_blocks_start_rewrite(self):
        """Tests partial response for generators with known content length,
        block reading from start, and Content-Length header rewritten."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") * 3 for x in range(10)),
            content_length=30,
            headers={"Content-Length": "30"},
        )
        res.make_partial([(0, 6)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 7
        assert res.headers.get("Content-Range") == "bytes 0-6/30"
        assert b"".join(gen) == b"0001112"

    def test_partial_known_length_blocks_range(self):
        """Tests partial response for generators with known content length and
        block reading within a range."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") * 3 for x in range(10)), content_length=30
        )
        res.make_partial([(8, 16)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 9
        assert res.headers.get("Content-Range") == "bytes 8-16/30"
        assert b"".join(gen) == b"233344455"

    def test_partial_known_length_blocks_range_rewrite(self):
        """Tests partial response for generators with known content length,
        block reading within a range, and Content-Length header rewritten."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") * 3 for x in range(10)),
            content_length=30,
            headers={"Content-Length": "30"},
        )
        res.make_partial([(8, 16)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 9
        assert res.headers.get("Content-Range") == "bytes 8-16/30"
        assert b"".join(gen) == b"233344455"

    def test_partial_known_length_blocks_range2(self):
        """Tests partial response for generators with known content length and
        block reading within a specific small range."""
        res = GeneratorResponse(
            (b"01234" for x in range(5)), content_length=25
        )
        res.make_partial([(7, 8)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 2
        assert res.headers.get("Content-Range") == "bytes 7-8/25"
        assert b"".join(gen) == b"23"

    def test_partial_known_length_blocks_end(self):
        """Tests partial response for generators with known content length and
        block reading from the end."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") * 3 for x in range(10)), content_length=30
        )
        res.make_partial([(None, 7)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 7
        assert res.headers.get("Content-Range") == "bytes 23-29/30"
        assert b"".join(gen) == b"7888999"

    def test_partial_known_length_blocks_end_rewrite(self):
        """Tests partial response for generators with known content length,
        block reading from the end, and Content-Length header rewritten."""
        res = GeneratorResponse(
            (str(x).encode("utf-8") * 3 for x in range(10)),
            content_length=30,
            headers={"Content-Length": "30"},
        )
        res.make_partial([(None, 7)])
        gen = res(start_response)
        assert int(res.headers.get("Content-Length")) == 7
        assert res.headers.get("Content-Range") == "bytes 23-29/30"
        assert b"".join(gen) == b"7888999"

    def test_partial_unknown_length_start(self):
        """Tests partial response for generators with unknown content length
        from a start byte, expecting HTTPException."""
        res = GeneratorResponse((str(x).encode("utf-8") for x in range(10)))
        res.make_partial([(7, None)])
        with pytest.raises(HTTPException):
            res(start_response)

    def test_partial_unknown_length_range(self):
        """Tests partial response for generators with unknown content length
        within a range, expecting HTTPException."""
        res = GeneratorResponse((str(x).encode("utf-8") for x in range(10)))
        res.make_partial([(7, 9)])
        with pytest.raises(HTTPException):
            res(start_response)
            # assert err.status_code == HTTP_RANGE_NOT_SATISFIABLE

    def test_partial_unknown_length_end(self):
        """Tests partial response for generators with unknown content length
        from the end, expecting HTTPException."""
        res = GeneratorResponse((str(x).encode("utf-8") for x in range(10)))
        res.make_partial([(None, 7)])
        with pytest.raises(HTTPException):
            res(start_response)
            # assert err.status_code == HTTP_RANGE_NOT_SATISFIABLE


class TestJSONResponse:
    """Tests for JSONResponse."""

    def test_kwargs(self):
        """Tests JSONResponse initialization with keyword arguments."""
        res = JSONResponse(items=list(range(5)))
        data = load(res(start_response))
        assert data == {"items": [0, 1, 2, 3, 4]}
        assert res.content_length == 26

    def test_charset(self):
        """Tests JSONResponse with a specified charset."""
        res = JSONResponse(msg="Message")
        res(start_response)
        assert res.headers["Content-Type"] == "application/json; charset=utf-8"

    def test_content_length(self):
        """Tests Content-Length header in JSONResponse."""
        res = JSONResponse(msg="Message")
        res(start_response)
        assert int(res.headers.get("Content-Length")) == 18

    def test_no_charset(self):
        """Tests JSONResponse when no charset is specified."""
        res = JSONResponse(msg="Message", charset=None)
        res(start_response)
        assert res.headers.get("Content-Type") == "application/json"

    def test_once(self):
        """Tests that a JSONResponse object can only be used once."""
        response = JSONResponse(msg="Message", charset=None)
        response(start_response)
        with pytest.raises(RuntimeError):
            response(start_response)

    def test_null(self):
        """Tests JSONResponse with null data."""
        response = JSONResponse()
        data = load(response(start_response))
        assert data is None

    def test_list_of_objects(self):
        """Tests JSONResponse with a list of objects."""
        response = JSONResponse([{"x": 1}, {"x": 2}])
        data = load(response(start_response))
        assert data == [{"x": 1}, {"x": 2}]

    def test_partial_content_start(self):
        """Tests partial content response for JSONResponse from the start."""
        response = JSONResponse([{"x": 1}, {"x": 2}])
        response.make_partial([(0, 4)])
        assert response(start_response).read() == b'[{"x"'

    def test_data_or_kwargs(self):
        """Tests that JSONResponse raises an error if both data_ and kwargs are
        provided."""
        with pytest.raises(RuntimeError):
            JSONResponse([], msg="Messgae")

    def test_no_decoded_unicode(self):
        """Tests JSONResponse with non-ASCII characters and
        ensure_ascii=False."""
        res = JSONResponse(
            msg="Čeština", encoder_kwargs={"ensure_ascii": False}
        )
        data = res.data
        assert data == b'{"msg": "\xc4\x8ce\xc5\xa1tina"}'


class TestTextResponse:
    """Tests for TextResponse."""

    def test_simple(self):
        """Tests a simple TextResponse."""
        res = TextResponse("Simple text")
        res.content_type = "text/plain; charset=utf-8"
        assert res.data == b"Simple text"
        assert res.content_length == 11

    def test_no_charset(self):
        """Tests TextResponse when no charset is specified."""
        res = TextResponse("Simple text", charset=None)
        res.content_type = "text/plain"
        assert res.data == b"Simple text"
        assert res.content_length == 11

    def test_content_length(self):
        """Tests Content-Length header in TextResponse."""
        res = TextResponse("Simple text")
        res(start_response)
        assert int(res.headers.get("Content-Length")) == 11


class TestGeneratorResponse:
    """Tests for GeneratorResponse classes."""

    def test_generator(self):
        """Tests a basic GeneratorResponse."""
        res = GeneratorResponse((str(x).encode("utf-8") for x in range(5)))
        gen = res(start_response)
        assert b"".join(gen) == b"01234"

    def test_str_generator(self):
        """Tests a StrGeneratorResponse."""
        res = StrGeneratorResponse((str(x) for x in range(5)))
        gen = res(start_response)
        assert b"".join(gen) == b"01234"

    def test_once(self):
        """Tests that a GeneratorResponse object can only be used once."""
        response = StrGeneratorResponse((str(x) for x in range(5)))
        response(start_response)
        with pytest.raises(RuntimeError):
            response(start_response)


class TestJSONGenerarorResponse:
    """Tests for JSONGeneratorResponse."""

    def test_generator(self):
        """Tests a JSONGeneratorResponse."""
        res = JSONGeneratorResponse(items=range(5))
        gen = res(start_response)
        data = loads(b"".join(gen))
        assert data == {"items": [0, 1, 2, 3, 4]}

    def test_charset(self):
        """Tests JSONGeneratorResponse with a specified charset."""
        res = JSONGeneratorResponse(items=range(5))
        res(start_response)
        assert res.headers["Content-Type"] == "application/json; charset=utf-8"

    def test_no_charset(self):
        """Tests JSONGeneratorResponse when no charset is specified."""
        res = JSONGeneratorResponse(items=range(5), charset=None)
        res(start_response)
        assert res.headers.get("Content-Type") == "application/json"

    def test_once(self):
        """Tests that a JSONGeneratorResponse object can only be used once."""
        response = JSONGeneratorResponse(items=range(5), charset=None)
        response(start_response)
        with pytest.raises(RuntimeError):
            response(start_response)


class TestRedirectResponse:
    """Tests for RedirectResponse and the redirect function."""

    def test_init(self):
        """Tests RedirectResponse initialization."""
        res = RedirectResponse("/", 303, message="See Other")
        assert res.status_code == 303
        assert res.data == b"See Other"
        assert res.headers["Location"] == "/"

    def test_init_deprecated(self):
        """Tests RedirectResponse initialization with deprecated arguments."""
        res = RedirectResponse("/true", True)
        assert res.status_code == 301
        assert res.headers["Location"] == "/true"

        res = RedirectResponse("/permanent", permanent=True)
        assert res.status_code == 301
        assert res.headers["Location"] == "/permanent"

    def test_redirect(self):
        """Tests the redirect function with default arguments."""
        with pytest.raises(HTTPException) as err:
            redirect("/")

        assert isinstance(err.value.response, RedirectResponse)
        assert err.value.response.status_code == 302

    def test_redirect_deprecated(self):
        """Tests the redirect function with deprecated arguments."""
        with pytest.raises(HTTPException) as err:
            redirect("/", True)

        assert isinstance(err.value.response, RedirectResponse)
        assert err.value.response.status_code == 301

        with pytest.raises(HTTPException) as err:
            redirect("/", permanent=True)

        assert isinstance(err.value.response, RedirectResponse)
        assert err.value.response.status_code == 301


class TestHTTPException:
    """Tests for HTTPException and other functions that raise it."""

    def test_redirect(self):
        """Tests HTTPException raised by redirect."""
        with pytest.raises(HTTPException) as err:
            redirect("/")

        assert err.value.status_code == 302

    def test_abort_status_code(self):
        """Tests abort with a status code."""
        with pytest.raises(HTTPException) as err:
            abort(404)

        assert err.value.status_code == 404

    def test_abort_response(self):
        """Tests abort with a Response object."""
        with pytest.raises(HTTPException) as err:
            abort(Response(status_code=400))

        assert isinstance(err.value.response, Response)
        assert err.value.status_code == 400

    def test_ordinary_exception(self):
        """Tests raising a simple HTTPException."""
        with pytest.raises(HTTPException) as err:
            raise HTTPException(500)

        assert err.value.status_code == 500


class TestFileResponse:
    """Tests for file type responses."""

    def test_assert_readable(self):
        """Tests that FileObjResponse asserts if the file object is not
        readable."""
        with pytest.raises(AssertionError):
            FileObjResponse(BufferedWriter(BytesIO()))

    def test_assert_text(self):
        """Tests that FileObjResponse asserts if the file object is a text
        stream."""
        with pytest.raises(AssertionError):
            with open(__file__, "rt", encoding="utf-8") as file_:
                FileObjResponse(file_)

    def test_last_modified_header(self):
        """Tests that FileResponse sets the Last-Modified header."""
        res = FileResponse(__file__)
        assert res.headers.get("Last-Modified") is not None

    def test_accept_range(self):
        """Tests that FileResponse sets the Accept-Ranges header."""
        res = FileResponse(__file__)
        assert res.headers.get("Accept-Ranges") == "bytes"

    def test_partial_content_start(self):
        """Tests partial content response for FileResponse from the start."""
        res = FileResponse(__file__)
        res.make_partial([(0, 4)])
        assert res(start_response).read() == b'"""Te'
        assert int(res.headers.get("Content-Length")) == 5

    def test_partial_content_mid(self):
        """Tests partial content response for FileResponse from the middle."""
        res = FileResponse(__file__)
        res.make_partial([(3, 6)])
        assert res(start_response).read() == b"Test"
        assert int(res.headers.get("Content-Length")) == 4

    def test_partial_content_last(self):
        """Tests partial content response for FileResponse requesting the last
        N bytes."""
        with open(__file__, "rb") as fh:
            last4 = fh.read()[-4:]
        res = FileResponse(__file__)
        res.make_partial([(None, 4)])
        assert res(start_response).read() == last4
        assert int(res.headers.get("Content-Length")) == 4


class TestNotModifiedResponse:
    """Tests for NotModifiedResponse."""

    def test_params(self):
        """Tests NotModifiedResponse initialization with various parameters."""
        res = NotModifiedResponse(
            etag='W/"etag"',
            content_location="content-location",
            date="22 Apr 2022",
            vary="yrav",
        )
        assert res.headers.get("ETag") == 'W/"etag"'
        assert res.headers.get("Content-Location") == "content-location"
        assert res.headers.get("Date") == "22 Apr 2022"
        assert res.headers.get("Vary") == "yrav"

    def test_date_time(self):
        """Tests NotModifiedResponse with a timestamp for the Date header."""
        res = NotModifiedResponse(date=0)
        assert res.headers.get("Date") == "Thu, 01 Jan 1970 00:00:00 GMT"

    def test_date_datetime(self):
        """Tests NotModifiedResponse with a datetime object for the Date
        header."""
        res = NotModifiedResponse(date=datetime.fromtimestamp(0, timezone.utc))
        assert res.headers.get("Date") == "Thu, 01 Jan 1970 00:00:00 GMT"

    def test_etag_only(self):
        """Tests NotModifiedResponse with only ETag specified."""
        res = NotModifiedResponse(etag='W/"cd04a47544"')
        assert res.headers.get("ETag") == 'W/"cd04a47544"'

    def test_date_empty_string(self):
        """Tests NotModifiedResponse when an empty string is provided for the
        Date header."""
        res = NotModifiedResponse(date="")
        assert res.headers.get("Date") is None

    def test_status_line_format(self):
        """304 response status line must be '304 Not Modified'."""
        received = []

        def capture(status, _headers):
            received.append(status)
            return lambda _data: None

        res = NotModifiedResponse(etag='"abc"')
        res(capture)
        assert received[0] == "304 Not Modified"


class TestStatusLineFormat:
    """Verify that all response types emit properly formatted status lines."""

    _status_re = re.compile(r"^\d{3} \S")

    def _capture(self):
        received = []

        def sr(status, _headers):
            received.append(status)
            return lambda _d: None

        return sr, received

    def test_response_200(self):
        """Response emits '200 OK' status line."""
        sr, received = self._capture()
        Response(b"hello")(sr)
        assert received[0] == "200 OK"

    def test_response_404(self):
        """Response with HTTP_NOT_FOUND emits '404 Not Found'."""
        sr, received = self._capture()
        Response(b"nope", status_code=HTTP_NOT_FOUND)(sr)
        assert received[0] == "404 Not Found"

    def test_redirect_302(self):
        """RedirectResponse emits '302 Found' status line."""
        sr, received = self._capture()
        RedirectResponse("/new")(sr)
        assert received[0] == "302 Found"

    def test_redirect_301(self):
        """RedirectResponse permanent emits '301 Moved Permanently'."""
        sr, received = self._capture()
        RedirectResponse("/new", 301)(sr)
        assert received[0] == "301 Moved Permanently"

    def test_partial_response(self):
        """PartialResponse emits '206 Partial Content' status line."""
        sr, received = self._capture()
        res = PartialResponse(b"56789")
        res.make_range([(5, 9)])
        res(sr)
        assert received[0] == "206 Partial Content"

    def test_no_content_response(self):
        """NoContentResponse emits '204 No Content' status line."""
        sr, received = self._capture()
        NoContentResponse()(sr)
        assert received[0] == "204 No Content"

    def test_status_line_pattern(self):
        """Status line must start with three digits followed by a space."""
        sr, received = self._capture()
        Response(b"data")(sr)
        assert self._status_re.match(received[0])

    def test_304_deny_headers_warning(self):
        """BaseResponse with status 304 warns when representation headers
        (Content-Type etc.) are present."""
        res = Response(
            headers={"Content-Type": "text/html", "ETag": '"abc"'},
            status_code=304,
        )
        with patch("poorwsgi.response.log") as mock_log:
            res(lambda _s, _h: lambda _d: None)
        warning_msgs = [str(call) for call in mock_log.warning.call_args_list]
        assert any("representation" in m for m in warning_msgs)

    def test_304_no_required_headers_warning(self):
        """BaseResponse with status 304 warns when none of Date/ETag/Vary/
        Content-Location are present."""
        res = Response(b"", status_code=304)
        with patch("poorwsgi.response.log") as mock_log:
            res(lambda _s, _h: lambda _d: None)
        warning_msgs = [str(call) for call in mock_log.warning.call_args_list]
        assert any("required" in m or "Missing" in m for m in warning_msgs)


class TestContentLengthAccuracy:
    """Content-Length header must exactly match the body length."""

    def test_response_bytes(self):
        """Content-Length matches byte body length."""
        body = b"Hello, World!"
        res = Response(body)
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) == len(body)

    def test_response_string_utf8(self):
        """Content-Length reflects encoded byte length for multi-byte chars."""
        text = "Čeština"
        body = text.encode("utf-8")
        res = Response(text)
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) == len(body)

    def test_response_write(self):
        """Content-Length is updated after calling write()."""
        res = Response(b"Hello")
        res.write(b" World")
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) == 11

    def test_json_response(self):
        """JSONResponse Content-Length matches the JSON-encoded body."""
        res = JSONResponse(x=1)
        body = res.data
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) == len(body)

    def test_partial_content_length(self):
        """Partial response Content-Length reflects the slice."""
        res = Response(b"0123456789")
        res.make_partial([(2, 5)])
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) == 4  # bytes 2,3,4,5

    def test_body_matches_content_length(self):
        """Actual bytes returned equal declared Content-Length."""
        res = Response(b"0123456789")
        buf = res(lambda _s, _h: lambda _d: None)
        data = buf.read()
        assert len(data) == 10


class TestIBytesIO:
    """Tests for IBytesIO helper class."""

    def test_read_kilo(self):
        """read_kilo returns up to 1024 bytes."""
        buf = IBytesIO(b"x" * 2048)
        chunk = buf.read_kilo()
        assert len(chunk) == 1024

    def test_iteration(self):
        """Iterating IBytesIO yields 1024-byte chunks."""
        buf = IBytesIO(b"y" * 2000)
        chunks = list(buf)
        assert len(chunks) == 2
        assert len(chunks[0]) == 1024
        assert len(chunks[1]) == 976


class TestBaseResponse:
    """Tests for BaseResponse standalone behavior."""

    def test_headers_setter_list(self):
        """Setting headers from a list creates a Headers instance."""
        res = BaseResponse()
        res.headers = [("X-Foo", "bar")]
        assert res.headers["X-Foo"] == "bar"

    def test_headers_setter_headers(self):
        """Setting headers from a Headers object keeps it as-is."""
        h = Headers([("X-Foo", "bar")])
        res = BaseResponse()
        res.headers = h
        assert res.headers["X-Foo"] == "bar"

    def test_data_property(self):
        """BaseResponse.data always returns empty bytes."""
        res = BaseResponse()
        assert res.data == b""

    def test_make_partial_non_200_status(self):
        """make_partial is a no-op when status_code is not 200."""
        res = BaseResponse(status_code=HTTP_NOT_FOUND)
        res.make_partial([(0, 10)])
        assert not res.ranges

    def test_make_range_non_206_status(self):
        """make_range is a no-op when status_code is not 206."""
        res = BaseResponse(status_code=HTTP_OK)
        res.make_range([(0, 10)])
        assert not res.ranges

    def test_add_header(self):
        """add_header delegates to the Headers object."""
        res = BaseResponse()
        res.add_header("X-Test", "value")
        assert res.headers["X-Test"] == "value"

    def test_status_code_invalid(self):
        """Setting an invalid status code raises ValueError."""
        res = BaseResponse()
        with pytest.raises(ValueError, match="Bad response status"):
            res.status_code = 999

    def test_status_code_setter_updates_reason(self):
        """Setting status_code updates the reason phrase automatically."""
        res = BaseResponse()
        res.status_code = HTTP_NOT_FOUND
        assert res.reason == "Not Found"

    def test_status_code_setter_clears_ranges(self):
        """Changing status_code away from 200/206 clears ranges."""
        res = BaseResponse()
        res.make_partial([(0, 10)])
        assert res.ranges  # ranges set
        res.status_code = HTTP_NOT_FOUND
        assert not res.ranges

    def test_make_partial_inconsistent_range(self):
        """make_partial logs a warning for end < start and skips the range."""
        res = BaseResponse()
        with patch("poorwsgi.response.log") as mock_log:
            res.make_partial([(10, 5)])  # end < start
        assert mock_log.warning.called
        assert not res.ranges

    def test_make_range_multiple_ranges_warning(self):
        """make_range logs a warning when more than one range is given."""
        res = Response(b"0123456789", status_code=HTTP_PARTIAL_CONTENT)
        with patch("poorwsgi.response.log") as mock_log:
            res.make_range([(0, 3), (5, 8)])
        warning_msgs = [str(c) for c in mock_log.warning.call_args_list]
        assert any("one range" in m for m in warning_msgs)

    def test_make_range_none_in_mixed_ranges(self):
        """make_range warns for None start/end and still uses valid range."""
        res = Response(b"0123456789", status_code=HTTP_PARTIAL_CONTENT)
        with patch("poorwsgi.response.log") as mock_log:
            res.make_range([(None, 5), (1, 3)])
        warning_msgs = " ".join(
            str(c) for c in mock_log.warning.call_args_list
        )
        assert "full range" in warning_msgs
        assert res.ranges == ((1, 3),)

    def test_make_range_inconsistent_in_mixed_ranges(self):
        """make_range warns for end < start and still uses the valid range."""
        res = Response(b"0123456789", status_code=HTTP_PARTIAL_CONTENT)
        with patch("poorwsgi.response.log") as mock_log:
            res.make_range([(10, 5), (1, 3)])
        warning_msgs = " ".join(
            str(c) for c in mock_log.warning.call_args_list
        )
        assert "Inconsistent" in warning_msgs
        assert res.ranges == ((1, 3),)


class TestNoContentAndDeclined:
    """Tests for NoContentResponse, EmptyResponse (deprecated), Declined."""

    def test_no_content_status(self):
        """NoContentResponse defaults to 204 No Content."""
        res = NoContentResponse()
        assert res.status_code == 204

    def test_no_content_call(self):
        """NoContentResponse emits empty header list via start_response."""
        received = []
        res = NoContentResponse()
        res(lambda s, h: received.append((s, h)) or (lambda _d: None))
        assert received[0][0] == "204 No Content"
        assert received[0][1] == []

    def test_empty_response_deprecated(self):
        """EmptyResponse emits a deprecation warning on construction."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            EmptyResponse()
        assert any(issubclass(warning.category, DeprecationWarning)
                   for warning in w)

    def test_declined_call_returns_empty(self):
        """Declined.__call__ returns an empty tuple without calling
        start_response."""
        called = []
        res = Declined()
        result = res(lambda _s, _h: called.append(1) or (lambda _d: None))
        assert not result
        assert not called

    def test_declined_headers_warning(self):
        """Setting headers on a Declined response logs a warning."""
        res = Declined()
        with patch("poorwsgi.response.log") as mock_log:
            res.headers = [("X-Foo", "bar")]
            assert mock_log.warning.called

    def test_declined_add_header_warning(self):
        """Calling add_header on a Declined response logs a warning."""
        res = Declined()
        with patch("poorwsgi.response.log") as mock_log:
            res.add_header("X-Foo", "bar")
            assert mock_log.warning.called


class TestHTTPExceptionMakeResponse:
    """Tests for HTTPException.make_response and response property."""

    def test_make_response_with_response(self):
        """make_response returns the wrapped response object."""
        inner = Response(b"body", status_code=201)
        exc = HTTPException(inner)
        assert exc.make_response() is inner

    def test_make_response_declined(self):
        """make_response for DECLINED returns a Declined instance."""
        exc = HTTPException(DECLINED)
        result = exc.make_response()
        assert isinstance(result, Declined)

    def test_make_response_200_returns_empty(self):
        """make_response for 200 returns an EmptyResponse."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            exc = HTTPException(HTTP_OK)
            result = exc.make_response()
        assert isinstance(result, EmptyResponse)

    def test_make_response_other_returns_none(self):
        """make_response for other status codes returns None."""
        exc = HTTPException(404)
        assert exc.make_response() is None

    def test_response_property_int(self):
        """response property returns None when arg is an int."""
        exc = HTTPException(404)
        assert exc.response is None

    def test_response_property_response(self):
        """response property returns the response when arg is a response."""
        inner = Response(b"body")
        exc = HTTPException(inner)
        assert exc.response is inner


class TestMakeResponse:
    """Tests for the make_response factory function."""

    def test_string_returns_response(self):
        """make_response with a string returns a Response."""
        res = make_response("Hello")
        assert isinstance(res, Response)
        assert res.data == b"Hello"

    def test_bytes_returns_response(self):
        """make_response with bytes returns a Response."""
        res = make_response(b"data")
        assert isinstance(res, Response)
        assert res.data == b"data"

    def test_dict_returns_json(self):
        """make_response with a dict returns a JSONResponse."""
        res = make_response({"key": "val"})
        assert isinstance(res, JSONResponse)
        assert b'"key"' in res.data

    def test_list_of_non_bytes_returns_json(self):
        """make_response with a list of non-bytes returns JSONResponse."""
        res = make_response([1, 2, 3])
        assert isinstance(res, JSONResponse)

    def test_list_of_bytes_returns_generator(self):
        """make_response with a list of bytes returns GeneratorResponse."""
        res = make_response([b"a", b"b"])
        assert isinstance(res, GeneratorResponse)

    def test_none_returns_no_content(self):
        """make_response with None returns NoContentResponse with 204."""
        res = make_response(None)
        assert isinstance(res, NoContentResponse)
        assert res.status_code == 204

    def test_none_explicit_status(self):
        """make_response with None and explicit status keeps that status."""
        res = make_response(None, status_code=201)
        assert res.status_code == 201

    def test_bytes_custom_status(self):
        """make_response passes status_code through to the Response."""
        res = make_response(b"err", status_code=HTTP_NOT_FOUND)
        assert res.status_code == HTTP_NOT_FOUND

    def test_invalid_raises_response_error(self):
        """make_response with an unsupported type raises ResponseError."""
        with pytest.raises(ResponseError):
            make_response(12345)


class TestRedirectHTTP:
    """HTTP-level tests for redirect responses."""

    def test_location_header(self):
        """RedirectResponse sets Location header to the given URL."""
        res = RedirectResponse("/new-path")
        res(lambda _s, _h: lambda _d: None)
        assert res.headers["Location"] == "/new-path"

    def test_redirect_function_location(self):
        """redirect() raises HTTPException with Location header set."""
        with pytest.raises(HTTPException) as exc_info:
            redirect("/target")
        exc_info.value.response(lambda _s, _h: lambda _d: None)
        assert exc_info.value.response.headers["Location"] == "/target"

    def test_redirect_message_body(self):
        """RedirectResponse body carries the supplied message text."""
        res = RedirectResponse("/go", message="Moved here")
        buf = res(lambda _s, _h: lambda _d: None)
        assert buf.read() == b"Moved here"

    def test_redirect_content_type(self):
        """RedirectResponse Content-Type is text/plain."""
        res = RedirectResponse("/go")
        res(lambda _s, _h: lambda _d: None)
        assert res.headers["Content-Type"] == "text/plain"


class TestFileResponseHTTP:
    """HTTP-level tests for file-based responses."""

    def test_last_modified_format(self):
        """Last-Modified header is in RFC 7231 date-time format."""
        rfc_re = re.compile(
            r"^[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT$"
        )
        res = FileResponse(__file__)
        assert rfc_re.match(res.headers["Last-Modified"])

    def test_accept_ranges_bytes(self):
        """FileResponse sets Accept-Ranges: bytes before calling response."""
        res = FileResponse(__file__)
        assert res.headers["Accept-Ranges"] == "bytes"

    def test_content_length_positive(self):
        """FileResponse Content-Length is positive."""
        res = FileResponse(__file__)
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) > 0

    def test_file_obj_response_bytesio(self):
        """FileObjResponse works with an in-memory BytesIO object."""
        buf = BytesIO(b"hello world")
        res = FileObjResponse(buf)
        res(lambda _s, _h: lambda _d: None)
        assert int(res.headers["Content-Length"]) == 11

    def test_file_obj_response_content_type_default(self):
        """FileObjResponse defaults Content-Type to
        application/octet-stream."""
        buf = BytesIO(b"data")
        res = FileObjResponse(buf)
        res(lambda _s, _h: lambda _d: None)
        assert res.headers["Content-Type"] == "application/octet-stream"

    def test_file_obj_response_data(self):
        """FileObjResponse.data reads file content from current position."""
        buf = BytesIO(b"hello")
        res = FileObjResponse(buf)
        assert res.data == b"hello"

    def test_file_obj_unknown_size(self):
        """FileObjResponse handles a stream with no fileno and no getbuffer,
        defaulting content_length to 0."""

        class _FakeStream(RawIOBase):
            def readable(self):
                return True

            def read(self, _n=-1):
                return b""

            def readinto(self, _b):
                return 0

            def seekable(self):
                return False

            def fileno(self):
                raise OSError("no fileno")

        stream = _FakeStream()
        with patch("poorwsgi.response.log"):
            res = FileObjResponse(stream)
        assert res.content_length == 0

    def test_file_obj_data_closed(self):
        """FileObjResponse.data returns b'' and logs warning when closed."""
        buf = BytesIO(b"hello")
        res = FileObjResponse(buf)
        buf.close()
        with patch("poorwsgi.response.log") as mock_log:
            result = res.data
        assert result == b""
        assert mock_log.warning.called

    def test_file_obj_data_non_seekable(self):
        """FileObjResponse.data returns b'' when file is not seekable."""

        class _NonSeekable(RawIOBase):
            def readable(self):
                return True

            def read(self, _n=-1):
                return b""

            def readinto(self, _b):
                return 0

            def seekable(self):
                return False

            def fileno(self):
                raise OSError("no fileno")

        stream = _NonSeekable()
        with patch("poorwsgi.response.log"):
            res = FileObjResponse(stream)
        with patch("poorwsgi.response.log") as mock_log:
            result = res.data
        assert result == b""
        assert mock_log.info.called

    def test_file_obj_end_of_response_closed(self):
        """FileObjResponse.__end_of_response__ returns empty IBytesIO and
        logs error when the underlying file has been closed."""
        buf = BytesIO(b"hello")
        res = FileObjResponse(buf)
        buf.close()
        with patch("poorwsgi.response.log") as mock_log:
            result = res.__end_of_response__()
        assert result.read() == b""
        assert mock_log.error.called

    def test_file_response_unreadable(self):
        """FileResponse raises IOError when the file is not readable."""
        with pytest.raises(IOError, match="Could not stat file"):
            FileResponse("/nonexistent/path/to/file.txt")

    def test_declined_headers_property(self):
        """Declined.headers property always returns a fresh empty Headers."""
        res = Declined()
        assert len(list(res.headers.items())) == 0


class TestResponseWrite:
    """Tests for Response.write() and data property edge cases."""

    def test_write_increases_content_length(self):
        """write() increases content_length by the written byte count."""
        res = Response(b"abc")
        assert res.content_length == 3
        res.write(b"de")
        assert res.content_length == 5

    def test_write_string(self):
        """write() accepts str and encodes it to UTF-8."""
        res = Response(b"")
        res.write("Čeština")
        assert res.content_length == len("Čeština".encode("utf-8"))

    def test_data_after_write(self):
        """data property reflects all bytes in the buffer after write()."""
        res = Response(b"")
        res.write(b"Hello World")
        assert res.data == b"Hello World"

    def test_data_closed_buffer_returns_empty(self):
        """data property returns b'' and logs warning when buffer is closed."""
        res = Response(b"hello")
        res._Response__buffer.close()  # pylint: disable=protected-access
        with patch("poorwsgi.response.log") as mock_log:
            result = res.data
        assert result == b""
        assert mock_log.warning.called

    def test_end_of_response_closed_buffer(self):
        """__end_of_response__ returns empty IBytesIO and logs error
        when buffer is closed."""
        res = Response(b"hello")
        res._Response__buffer.close()  # pylint: disable=protected-access
        with patch("poorwsgi.response.log") as mock_log:
            result = res.__end_of_response__()
        assert result.read() == b""
        assert mock_log.error.called
