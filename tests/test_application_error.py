"""Unit test for Unicode decode error propagation."""
from io import BytesIO
from time import time

import pytest

from poorwsgi.request import Request
from poorwsgi.wsgi import Application


def test_keyerror_on_internal_error(monkeypatch):
    """Tests for KeyError: 'args' on Unicode decode error in the path."""
    app = Application()

    def mock_path(self):
        """Mock of the old Request.path property."""
        # We are mocking the old behavior, where UnicodeDecodeError was not
        # caught inside the path property and propagated to the __request__
        # method.
        raise UnicodeDecodeError("utf-8", b"\xc0", 0, 1, "invalid start byte")

    monkeypatch.setattr(Request, "path", property(mock_path))

    environ = {
        "PATH_INFO": "/foo",
        "REQUEST_METHOD": "GET",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(b""),
        "wsgi.errors": BytesIO(),
        "REQUEST_STARTTIME": time(),
    }

    def start_response(*_):
        # This is mock, we check response from app call
        pass

    with pytest.raises(UnicodeDecodeError, match="invalid start byte"):
        app(environ, start_response)
