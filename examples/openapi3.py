"""This is example and test application for PoorWSGI connector with openapi3
support.

This sample testing example is free to use, modify and study under same BSD
licence as PoorWSGI. So enjoy it ;)
"""

from wsgiref.simple_server import make_server
from os import urandom, path
from sys import path as python_path

import logging as log
import json

from openapi_core import (
        Spec,
        unmarshal_request, unmarshal_response,
        )

from openapi_core.exceptions import OpenAPIError
from openapi_core.templating.paths.exceptions import PathNotFound, \
    OperationNotFound
from openapi_core.validation.request.exceptions import SecurityValidationError

TEST_PATH = path.dirname(__file__)
python_path.insert(0, path.abspath(
    path.join(TEST_PATH, path.pardir)))

# pylint: disable = wrong-import-position

from poorwsgi import Application, state  # noqa
from poorwsgi.response import Response, abort, HTTPException, \
    JSONResponse  # noqa
from poorwsgi.request import Request  # noqa
from poorwsgi.openapi_wrapper import OpenAPIRequest, \
    OpenAPIResponse  # noqa
from poorwsgi.session import PoorSession  # noqa

XXX = 'xxx'
app = application = Application("OpenAPI3 Test App")
app.debug = True
app.secret_key = urandom(32)     # random key each run


options_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "1728000",        # 20 days
    "Content-Length": "0"
}


with open(path.join(path.dirname(__file__), "openapi.json"),
          "r", encoding="utf-8") as openapi:
    app.openapi_spec = Spec.from_dict(json.load(openapi))  # type: ignore


@app.before_response()
def cors_request(req):
    """CORS additional response for method OPTIONS."""
    if req.uri.startswith("/p/"):
        return      # endpoints for printers does not need CORS
    if req.method_number == state.METHOD_OPTIONS:
        res = Response(content_type="text/plain; charset=UTF-8",
                       headers=options_headers,
                       status_code=state.HTTP_NO_CONTENT)
        raise HTTPException(res)


@app.after_response()
def cors_response(req, res):
    """CORS additional headers in response."""
    if isinstance(req, Request):
        res.add_header("Access-Control-Allow-Origin",
                       req.headers.get("Origin", "*"))
        res.add_header("Access-Control-Allow-Credentials", "true")
    return res


@app.before_response()
def before_each_response(req):
    """Check API before process each response."""
    req.api = OpenAPIRequest(req)
    try:
        unmarshal_request(req.api, app.openapi_spec)
    except (OperationNotFound, PathNotFound) as error:
        log.debug("%s", error)
        return  # not found

    except SecurityValidationError as error:
        abort(JSONResponse(error=str(error), status_code=401,
                           charset=None))
    except OpenAPIError as error:
        abort(JSONResponse(error=str(error), status_code=400,
                           charset=None))


@app.after_response()
def after_each_response(req, res):
    """Check if ansewer is valid by OpenAPI."""
    if not hasattr(req, "api"):
        req.api = OpenAPIRequest(req)
    try:
        unmarshal_response(
                req.api,
                OpenAPIResponse(res),
                app.openapi_spec)
    except (OperationNotFound, PathNotFound):
        return res
    except OpenAPIError as error:
        log.error("API output error: %s", str(error))
        raise
    return res


@app.route("/plain_text")
def plain_text(req):
    """Simple hello world example."""
    assert req
    return "Hello world", "text/plain"


@app.route("/response")
def response_handler(req):
    """Override content-type via header value."""
    assert req
    return Response(
        status_code=200,
        headers={'Content-Type': 'application/json'},
        data=b"{}")


@app.route("/json/<arg>")
def ajax_arg(req, arg):
    """Ajax JSON example."""
    assert req
    return json.dumps({"arg": arg}), "application/json"


@app.route('/json', method=state.METHOD_POST | state.METHOD_PUT)
def test_json(req):
    """JSONResponse example"""
    assert req
    return JSONResponse(status_code=418, message="I'm teapot :-)",
                        request=req.json)


@app.route("/arg/<arg:int>")
def ajax_integer(req, arg):
    """Simple JSON response with integer argument in path."""
    assert req
    return json.dumps({"arg": arg}), "application/json"


@app.route("/arg/<arg:float>")
def ajax_float(req, arg):
    """Simple JSON response with float argument in path."""
    assert req
    return json.dumps({"arg": arg}), "application/json"


@app.route("/arg/<arg:uuid>")
def ajax_uuid(req, arg):
    """Simple JSON response with uuid argument in path."""
    assert req
    return json.dumps({"arg": str(arg)}), "application/json"


@app.route('/internal-server-error')
def method_raises_errror(req):
    """Internal server error test."""
    assert req
    raise RuntimeError('Test of internal server error')


@app.route('/login')
def login(req):
    """Set login cookie test."""
    assert req
    cookie = PoorSession(app.secret_key)
    cookie.data['login'] = True
    response = Response(status_code=204)
    cookie.header(response)
    return response


@app.route('/check/login')
def check_login(req):
    """Clear login cookie - logout test."""
    session = PoorSession(app.secret_key)
    session.load(req.cookies)
    if 'login' not in session.data:
        raise HTTPException(401)
    return "login ok"


@app.route('/check/api-key')
def check_api_key(req):
    """API-Key secrets test."""
    api_token = req.headers.get("API-Key", None)
    if api_token != XXX:
        raise HTTPException(401)
    return "api-key ok"


@app.http_state(state.HTTP_NOT_FOUND)
def not_found(req):
    """404 NotFound test."""
    return (json.dumps(
        {"error": f"Url {req.uri}, you are request not found"}),
        "application/json", None, 404)


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on 127.0.0.1:8080")
    httpd.serve_forever()
