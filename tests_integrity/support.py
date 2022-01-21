from sys import stderr, executable
from warnings import warn
from time import sleep
from subprocess import Popen
from socket import socket, error as SocketError

from requests import Request, Session
from requests.exceptions import RequestException
from openapi_core.exceptions import OpenAPIResponseError  # type: ignore
from openapi_core.templating.paths.exceptions import (  # type: ignore
    PathNotFound, OperationNotFound, ServerNotFound)

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
        raise RuntimeError("Server not started in 10 seconds")

    return process


def check_url(url, method="GET", status_code=200, allow_redirects=True,
              **kwargs):
    """Do HTTP request and check status_code."""
    session = kwargs.pop("session", None)
    if not session:     # nechceme vytvářet session nadarmo
        session = Session()
    try:
        request = Request(method, url, cookies=session.cookies, **kwargs)
        response = session.send(request.prepare(),
                                allow_redirects=allow_redirects)
        if isinstance(status_code, int):
            status_code = [status_code]
        assert response.status_code in status_code, \
               response.text or response.reason
        return response
    except RequestException:
        pass
    raise ConnectionError("Not response")


def check_api(url, method="GET", status_code=200, path_pattern=None,
              response_validator=None, **kwargs):
    """Do HTTP API request and check status_code."""
    assert response_validator, "response_validator must be set"
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
        api_request = OpenAPIRequest(request, path_pattern)
        result = response_validator.validate(api_request,
                                             OpenAPIResponse(response))
        if result.errors:
            to_raise = False
            for error in result.errors:
                if isinstance(error, (PathNotFound, OperationNotFound)):
                    if response.status_code == 404:
                        continue
                    warn(UserWarning("Not API definition for %s!" % url))
                    continue
                if isinstance(error, OpenAPIResponseError):
                    warn(UserWarning(
                        "API response error %d definition for %s: %s"
                        % (response.status_code, url, error)))
                    continue
                if isinstance(error, ServerNotFound):
                    continue    # just ignore
                stderr.write("API output error: %s" % str(error))
                to_raise = True
            if to_raise:
                raise TestError("API errors not zero: %d" % len(result.errors))
        return response
    except RequestException as err:
        print(err)
    raise ConnectionError("Not response")
