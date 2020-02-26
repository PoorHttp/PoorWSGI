from json import load, loads

import pytest

from poorwsgi.response import Response, JSONResponse, \
    GeneratorResponse, StrGeneratorResponse, JSONGeneratorResponse
from poorwsgi.request import Headers
from poorwsgi.state import HTTP_NOT_FOUND


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
    pass


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
    def test_args(self, response_args):
        res = response_args(start_response)
        assert isinstance(res.read(), bytes)

    def test_kwargs(self, response_kwargs):
        res = response_kwargs(start_response)
        assert isinstance(res.read(), bytes)


class TestJSONResponse:
    def test_kwargs(self):
        res = JSONResponse(items=list(range(5)))
        data = load(res(start_response))
        assert data == {"items": [0, 1, 2, 3, 4]}

    def test_charset(self):
        res = JSONResponse(msg="Message")

        def start_response(data, headers):
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json; charset=utf-8"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)

    def test_no_charset(self):
        res = JSONResponse(msg="Message", charset=None)

        def start_response(data, headers):
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)


class TestGeneratorResponse:
    def test_generator(self):
        res = GeneratorResponse((str(x).encode("utf-8") for x in range(5)))
        gen = res(start_response)
        assert b"".join(gen) == b"01234"

    def test_str_generator(self):
        res = StrGeneratorResponse((str(x) for x in range(5)))
        gen = res(start_response)
        assert b"".join(gen) == b"01234"


class TestJSONGenerarorResponse:
    def test_generator(self):
        res = JSONGeneratorResponse(items=range(5))
        gen = res(start_response)
        data = loads(b"".join(gen))
        assert data == {"items": [0, 1, 2, 3, 4]}

    def test_charset(self):
        res = JSONGeneratorResponse(items=range(5))

        def start_response(data, headers):
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json; charset=utf-8"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)

    def test_no_charset(self):
        res = JSONGeneratorResponse(items=range(5), charset=None)

        def start_response(data, headers):
            for key, val in headers:
                if key == "Content-Type":
                    assert val == "application/json"
                    raise Found()
        with pytest.raises(Found):
            res(start_response)
