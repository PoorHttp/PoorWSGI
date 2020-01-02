import pytest

from poorwsgi.response import Response
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
