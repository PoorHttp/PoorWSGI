from os import environ
from os.path import dirname, join, pardir
from sys import executable
from subprocess import Popen
from time import sleep
from socket import socket, error as SocketError

from pytest import fixture

from . support import check_url


@fixture(scope="module")
def url(request):
    url = environ.get("TEST_OPENAPI_URL", "").strip('/')
    if url:
        return url

    process = None
    print("Starting wsgi application...")
    if request.config.getoption("--with-uwsgi"):
        process = Popen(["uwsgi", "--plugin", "python3",
                         "--http-socket", "localhost:8080", "--wsgi-file",
                         join(dirname(__file__), pardir,
                              "examples/openapi3.py")])
    else:
        process = Popen([executable,
                         join(dirname(__file__), pardir,
                              "examples/openapi3.py")])

    assert process is not None
    connect = False
    for i in range(20):
        sck = socket()
        try:
            sck.connect(("localhost", 8080))
            connect = True
            break
        except SocketError:
            sleep(0.1)
        finally:
            sck.close()
    if not connect:
        process.kill()
        raise RuntimeError("Server not started in 2 seconds")

    yield "http://localhost:8080"  # server is running
    process.kill()


class TestOpenAPI():
    def test_plain_text(self, url):
        res = check_url(url+"/plain_text")
        assert res.headers["Content-Type"] == "text/plain"

    def test_json_arg_integer(self, url):
        res = check_url(url+"/json/42")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '42'

    def test_json_arg_float(self, url):
        res = check_url(url+"/json/3.14")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("arg") == '3.14'

    def test_json_arg_string(self, url):
        res = check_url(url+"/json/ok", status_code=400)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_arg_integer(self, url):
        res = check_url(url+"/arg/42")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("integer_arg") == 42

    def test_arg_float(self, url):
        res = check_url(url+"/arg/3.14")
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("float_arg") == 3.14

    def test_arg_string(self, url):
        res = check_url(url+"/arg/ok", status_code=404)
        assert res.headers["Content-Type"] == "application/json"
        data = res.json()
        assert data.get("error") is not None

    def test_native_not_found(self, url):
        check_url(url+"/notexists_url", status_code=404)

    def test_native_method_not_allowed(self, url):
        check_url(url+"/plain_text", method="DELETE", status_code=405)
