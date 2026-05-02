"""WebSocket example tests."""
from os import environ
from os.path import dirname, join, pardir
from uuid import uuid1
from base64 import encodebytes

from pytest import fixture
# websocket-client
from websocket import WebSocket

from . support import start_server, check_url

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use


@fixture(scope="module")
def server(request):
    """Fixture for starting the WebSocket example server."""
    process = None
    value = environ.get("TEST_WEBSOCKET_URL", "").rstrip('/')
    if value:
        yield value
    else:
        process = start_server(
            request,
            join(dirname(__file__), pardir, 'examples/websocket.py'),
            close=False)
        yield "localhost:8080"  # server is running

    if process is not None:
        process.kill()
        process.wait()


@fixture(scope="module")
def http_url(server):
    """Fixture for the HTTP URL of the server."""
    return f"http://{server}"


@fixture(scope="module")
def ws_url(server):
    """Fixture for the WebSocket URL of the server."""
    return f"ws://{server}"


class TestWebSocket:
    """Tests for the WebSocket example."""

    def test_upgrade(self, http_url):
        """Tests the WebSocket upgrade handshake."""
        uuid = uuid1().bytes
        check_url(http_url+"/ws", status_code=101,
                  headers={"Connection": "Upgrade",
                           "Upgrade": "websocket",
                           "Sec-WebSocket-Version": "13",
                           "Sec-WebSocket-Key":
                           encodebytes(uuid).decode().strip()})

    def test_websocket(self, ws_url):
        """Tests basic WebSocket communication."""
        # python websocket library breaks usage websocket-client with pylint
        # pylint: disable=no-member
        wsck = WebSocket()
        wsck.connect(ws_url+"/ws")
        msg = wsck.recv()
        assert msg.endswith("Hello")
        wsck.send("Test")
        msg = wsck.recv()
        assert msg.endswith("<b>Test</b>")
        wsck.close()
