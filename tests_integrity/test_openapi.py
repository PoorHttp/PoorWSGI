from os import environ
from os.path import dirname, join, pardir
from sys import executable
from subprocess import Popen
from time import sleep
from socket import socket, error as SocketError

from . support import check_url

URL = environ.get("TEST_OPENAPI_URL", "").strip('/')
PROCESS = None


def setUpModule():
    global PROCESS
    global URL

    if not URL:
        URL = "http://localhost:8080"
        print("Starting wsgi application...")
        PROCESS = Popen([executable,
                         join(dirname(__file__), pardir,
                              "examples/openapi3.py")])
        assert PROCESS is not None
        for i in range(20):
            sck = socket()
            try:
                sck.connect(("localhost", 8080))
                return
            except SocketError:
                sleep(0.1)
            finally:
                sck.close()
        raise RuntimeError("Server not started in 2 seconds")


def tearDownModule():
    PROCESS.kill()


class TestOpenAPI():
    def test_plain_text(self):
        res = check_url(URL+"/plain_text")
        assert res.headers["Content-Type"] == "text/plain"

    def test_json_arg_integer(self):
        res = check_url(URL+"/json/42")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '42'

    def test_json_arg_float(self):
        res = check_url(URL+"/json/3.14")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '3.14'

    def test_json_arg_string(self):
        res = check_url(URL+"/json/ok", status_code=400)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_arg_integer(self):
        res = check_url(URL+"/arg/42")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("integer_arg") == 42

    def test_arg_float(self):
        res = check_url(URL+"/arg/3.14")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("float_arg") == 3.14

    def test_arg_string(self):
        res = check_url(URL+"/arg/ok", status_code=404)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None
