"""Test for Response objects and it's functionality."""
from io import BufferedWriter, BytesIO

from simplejson import load, loads

import pytest

from poorwsgi.response import Response, JSONResponse, TextResponse, \
    GeneratorResponse, StrGeneratorResponse, JSONGeneratorResponse, \
    RedirectResponse, FileObjResponse, HTTPException, redirect, abort
from poorwsgi.request import Headers
from poorwsgi.state import HTTP_NOT_FOUND

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name


args = (
    ("<html></html>",),
    (b"<html></html>",),
    ("text", "text/plain"),
    (b"data", "application/octet-stream"),
    ("text", "text/plain", (("X-Header", "Value"),)),
    ("text", "text/plain", Headers((("X-Header", "Value"),))),
    ("text", "text/plain", Headers((("X-Header", "Value"),)), HTTP_NOT_FOUND)
)

kwargs = (
    {"data": "<html></html>"},
    {"data": "<html></html>"},
    {"content_type": "text/plain"},
    {"headers": (("X-Header", "Value"),)},
    {"status_code": HTTP_NOT_FOUND}
)


class Found(Exception):
    """Support exception for tests, just like StopIteration."""


@pytest.fixture(params=args)
def response_args(request):
    return Response(*request.param)


@pytest.fixture(params=kwargs)
def response_kwargs(request):
    return Response(**request.param)


def write(data):
    assert isinstance(data, bytes)
    assert False


def start_response(data, headers):
    assert isinstance(data, str)
    assert isinstance(headers, list)
    return write


class TestReponse:
    """Basic tests for Response."""
    def test_args(self, response_args):
        res = response_args(start_response)
        assert isinstance(res.read(), bytes)

    def test_kwargs(self, response_kwargs):
        res = response_kwargs(start_response)
        assert isinstance(res.read(), bytes)

    def test_once(self, response_args):
        response_args(start_response)
        with pytest.raises(RuntimeError):
            response_args(start_response)


class TestJSONResponse:
    """Tests for JSONResponse."""
    def test_kwargs(self):
        res = JSONResponse(items=list(range(5)))
        data = load(res(start_response))
        assert data == {"items": [0, 1, 2, 3, 4]}

    def test_charset(self):
        res = JSONResponse(msg="Message")

        def start_response(data, headers):
            assert data
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json; charset=utf-8"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)

    def test_no_charset(self):
        res = JSONResponse(msg="Message", charset=None)

        def start_response(data, headers):
            assert data
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)

    def test_once(self):
        response = JSONResponse(msg="Message", charset=None)
        response(start_response)
        with pytest.raises(RuntimeError):
            response(start_response)


class TestTextResponse:
    """Test for TextResponse."""
    def test_simple(self):
        res = TextResponse("Simple text")
        res.content_type = "text/plain; charset=utf-8"
        assert res.data == b"Simple text"

    def test_no_charset(self):
        res = TextResponse("Simple text", charset=None)
        res.content_type = "text/plain"
        assert res.data == b"Simple text"


class TestGeneratorResponse:
    """Tests for GeneratorResponse classes."""
    def test_generator(self):
        res = GeneratorResponse((str(x).encode("utf-8") for x in range(5)))
        gen = res(start_response)
        assert b"".join(gen) == b"01234"

    def test_str_generator(self):
        res = StrGeneratorResponse((str(x) for x in range(5)))
        gen = res(start_response)
        assert b"".join(gen) == b"01234"

    def test_once(self):
        response = StrGeneratorResponse((str(x) for x in range(5)))
        response(start_response)
        with pytest.raises(RuntimeError):
            response(start_response)


class TestJSONGenerarorResponse:
    """Test. for JSONGeneratorResponse."""
    def test_generator(self):
        res = JSONGeneratorResponse(items=range(5))
        gen = res(start_response)
        data = loads(b"".join(gen))
        assert data == {"items": [0, 1, 2, 3, 4]}

    def test_charset(self):
        res = JSONGeneratorResponse(items=range(5))

        def start_response(data, headers):
            assert data
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json; charset=utf-8"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)

    def test_no_charset(self):
        res = JSONGeneratorResponse(items=range(5), charset=None)

        def start_response(data, headers):
            assert data
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)

    def test_once(self):
        response = JSONGeneratorResponse(items=range(5), charset=None)
        response(start_response)
        with pytest.raises(RuntimeError):
            response(start_response)


class TestRedirectResponse:
    """Test for RedirectResponse and redirect function."""
    def test_init(self):
        res = RedirectResponse('/', 303, message='See Other')
        assert res.status_code == 303
        assert res.data == b'See Other'
        assert res.headers['Location'] == '/'

    def test_init_deprecated(self):
        res = RedirectResponse('/true', True)
        assert res.status_code == 301
        assert res.headers['Location'] == '/true'

        res = RedirectResponse('/permanent', permanent=True)
        assert res.status_code == 301
        assert res.headers['Location'] == '/permanent'

    def test_redirect(self):
        with pytest.raises(HTTPException) as err:
            redirect('/')

        assert isinstance(err.value.response, RedirectResponse)
        assert err.value.response.status_code == 302

    def test_redirect_deprecated(self):
        with pytest.raises(HTTPException) as err:
            redirect('/', True)

        assert isinstance(err.value.response, RedirectResponse)
        assert err.value.response.status_code == 301

        with pytest.raises(HTTPException) as err:
            redirect('/', permanent=True)

        assert isinstance(err.value.response, RedirectResponse)
        assert err.value.response.status_code == 301


class TestHTTPException:
    """Tests for HTTPException and other functions which raise that."""

    def test_redirect(self):
        with pytest.raises(HTTPException):
            redirect('/')

    def test_abort_status_code(self):
        with pytest.raises(HTTPException) as err:
            abort(404)

        assert err.value.args[0] == 404

    def test_abort_response(self):
        with pytest.raises(HTTPException) as err:
            abort(Response(status_code=400))

        assert isinstance(err.value.response, Response)
        assert err.value.response.status_code == 400


class TestFileResponse():
    """Tests for file type responses."""

    def test_assert_readable(self):
        with pytest.raises(AssertionError):
            FileObjResponse(BufferedWriter(BytesIO()))

    def test_assert_text(self):
        with pytest.raises(AssertionError):
            with open(__file__, 'rt') as file_:
                FileObjResponse(file_)
