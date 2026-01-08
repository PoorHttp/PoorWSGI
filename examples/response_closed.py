#!/usr/bin/env python3
"""Example demonstrating Response with closed buffer scenario."""

from poorwsgi import Application
from poorwsgi.response import Response

app = Application("response_closed")


@app.route("/test")
def test_handler(_):
    """Simple test handler that returns a Response."""
    res = Response("Test data")
    # After response is sent, the buffer will be closed by WSGI server
    # Accessing res.data after that should be handled gracefully
    return res


@app.route("/test-after-response")
def test_after_response(_):
    """Handler that tries to access response data after creation."""
    res = Response("Test data")
    # Try to access data property immediately (should work)
    data = res.data
    # Just verify it works, don't log
    assert data == b"Test data"
    return res


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    print("Starting server on http://localhost:8080")
    httpd = make_server("localhost", 8080, app)
    httpd.serve_forever()
