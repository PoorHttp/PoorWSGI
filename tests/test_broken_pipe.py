"""Unit test for BrokenPipeError handling."""
from io import BytesIO
from time import time

import pytest

from poorwsgi.response import Response
from poorwsgi.wsgi import Application


@pytest.fixture
def base_environ():
    """Create a base WSGI environ dict for testing."""
    return {
        "PATH_INFO": "/test",
        "REQUEST_METHOD": "GET",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(b""),
        "wsgi.errors": BytesIO(),
        "REQUEST_STARTTIME": time(),
    }


def test_broken_pipe_on_response_send(base_environ):
    """Test that BrokenPipeError during response send is handled gracefully."""
    app = Application("test_broken_pipe")

    @app.route('/test')
    def test_handler(req):
        return "Hello World"

    def start_response_broken(*_):
        """Mock start_response that raises BrokenPipeError."""
        raise BrokenPipeError("Client disconnected")

    # The application should handle BrokenPipeError and return empty iterable
    result = app(base_environ, start_response_broken)
    assert result == ()


def test_connection_reset_on_response_send(base_environ):
    """Test that ConnectionResetError during response send is handled gracefully."""
    app = Application("test_connection_reset")

    @app.route('/test')
    def test_handler(req):
        return "Hello World"

    def start_response_reset(*_):
        """Mock start_response that raises ConnectionResetError."""
        raise ConnectionResetError("Connection reset by peer")

    # The application should handle ConnectionResetError and return empty iterable
    result = app(base_environ, start_response_reset)
    assert result == ()


def test_connection_aborted_on_response_send(base_environ):
    """Test that ConnectionAbortedError during response send is handled gracefully."""
    app = Application("test_connection_aborted")

    @app.route('/test')
    def test_handler(req):
        return "Hello World"

    def start_response_aborted(*_):
        """Mock start_response that raises ConnectionAbortedError."""
        raise ConnectionAbortedError("Software caused connection abort")

    # The application should handle ConnectionAbortedError and return empty iterable
    result = app(base_environ, start_response_aborted)
    assert result == ()


def test_broken_pipe_during_iteration(base_environ):
    """Test that BrokenPipeError during response iteration is handled gracefully."""
    app = Application("test_broken_pipe_iteration")

    @app.route('/test')
    def test_handler(req):
        return "Hello World"

    # Monkey-patch the Response class to raise BrokenPipeError
    original_call = Response.__call__

    def broken_call(self, start_response):
        start_response("200 OK", [])
        raise BrokenPipeError("Broken pipe during iteration")

    Response.__call__ = broken_call

    try:
        # The application should handle BrokenPipeError and return empty iterable
        result = app(base_environ, lambda *args: None)
        assert result == ()
    finally:
        # Restore original __call__ method
        Response.__call__ = original_call


def test_normal_response_still_works(base_environ):
    """Test that normal responses still work after adding BrokenPipeError handling."""
    app = Application("test_normal_response")

    @app.route('/test')
    def test_handler(req):
        return "Hello World"

    response_data = []

    def start_response(status, headers):
        """Normal start_response that collects response data."""
        response_data.append((status, headers))

    # Normal response should still work
    result = app(base_environ, start_response)
    assert result is not None
    assert len(response_data) == 1
    assert "200" in response_data[0][0]
