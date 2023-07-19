"""Support library for integrity tests."""
from sys import stderr, executable
from warnings import warn
from time import sleep
from subprocess import Popen
from socket import socket, error as SocketError

from requests import Request, Session
from requests.exceptions import RequestException
from openapi_core import unmarshal_response
from openapi_core.contrib.requests import (RequestsOpenAPIRequest,
                                           RequestsOpenAPIResponse)
from openapi_core.exceptions import OpenAPIError
from openapi_core.templating.paths.exceptions import PathNotFound


from . openapi import OpenAPIRequest, OpenAPIResponse


class TestError(RuntimeError):
    """Support exception."""


def start_server(request, example):
    """Start web server with example."""

    process = None
    print("Starting wsgi application...")
    if request.config.getoption("--with-uwsgi"):
        process = Popen(["uwsgi", "--plugin", "python3",
                         "--http-socket", "localhost:8080", "--wsgi-file",
                         example])
    else:
        # pylint: disable=consider-using-with
        process = Popen([executable, example])

    assert process is not None
    connect = False
    for i in range(100):  # pylint: disable=unused-variable
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
        process.wait()
        raise RuntimeError("Server not started in 10 seconds")

    return process


def check_url(url, method="GET", status_code=200, allow_redirects=True,
              **kwargs):
    """Do HTTP request and check status_code."""
    session = kwargs.pop("session", None)
    timeout = kwargs.pop("timeout", None)
    if not session:     # nechceme vytvářet session nadarmo
        session = Session()
    try:
        request = Request(method, url, cookies=session.cookies, **kwargs)
        response = session.send(request.prepare(),
                                allow_redirects=allow_redirects,
                                timeout=timeout)
        if isinstance(status_code, int):
            status_code = [status_code]
        assert response.status_code in status_code, \
               response.text or response.reason
        return response
    except RequestException:
        pass
    raise ConnectionError("Not response")


def check_api(url, method="GET", status_code=200,
              response_spec=None, **kwargs):
    """Do HTTP API request and check status_code."""
    assert response_spec, "response_validator must be set"
    session = kwargs.pop("session", None)
    if not session:
        session = Session()
    try:
        request = Request(method, url, **kwargs)
        response = session.send(session.prepare_request(request))
        # will be print only on error
        print("Response:\n", response.headers, "\n", response.text)
        if isinstance(status_code, int):
            status_code = [status_code]
        assert response.status_code in status_code
        try:
            unmarshal_response(
                    RequestsOpenAPIRequest(request),
                    RequestsOpenAPIResponse(response),
                    response_spec)
        except PathNotFound:
            if response.status_code == 404:
                return response
            warn(UserWarning(f"Not API definition for {url}!"))
            return response
        except OpenAPIError as error:
            stderr.write("API output error: {str(error)}")
            raise TestError("API error: {error}") from error
        return response
    except RequestException as err:
        print(err)
    raise ConnectionError("Not response")
