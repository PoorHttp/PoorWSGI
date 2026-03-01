"""Tests for Response objects and their functionality."""

from datetime import datetime, timezone
from io import BufferedWriter, BytesIO

import pytest
from simplejson import load, loads

from poorwsgi.request import Headers
from poorwsgi.response import (
    FileObjResponse,
    FileResponse,
    GeneratorResponse,
    HTTPException,
    JSONGeneratorResponse,
    JSONResponse,
    NotModifiedResponse,
    PartialResponse,
    RedirectResponse,
    Response,
    StrGeneratorResponse,
    TextResponse,
    abort,
    redirect,
)
from poorwsgi.state import HTTP_NOT_FOUND  # , HTTP_RANGE_NOT_SATISFIABLE

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use


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
        res = FileResponse(__file__)
        res.make_partial([(None, 4)])
        assert res(start_response).read() == b"one\n"
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
