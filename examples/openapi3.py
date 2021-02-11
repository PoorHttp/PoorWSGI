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

from openapi_core import create_spec  # type: ignore
from openapi_core.validation.request.validators import (  # type: ignore
        RequestValidator)
from openapi_core.validation.response.validators import (  # type: ignore
        ResponseValidator)
from openapi_core.validation.exceptions import InvalidSecurity  # type: ignore
from openapi_core.schema.operations.exceptions import (  # type: ignore
        InvalidOperation)
from openapi_core.schema.paths.exceptions import InvalidPath  # type: ignore
from openapi_core.templating.paths.exceptions import (  # type: ignore
    PathNotFound, OperationNotFound)

TEST_PATH = path.dirname(__file__)              # noqa
python_path.insert(0, path.abspath(             # noqa
    path.join(TEST_PATH, path.pardir)))

from poorwsgi import Application, state
from poorwsgi.response import Response, abort, HTTPException, JSONResponse
from poorwsgi.openapi_wrapper import OpenAPIRequest, OpenAPIResponse
from poorwsgi.session import PoorSession

app = application = Application("OpenAPI3 Test App")
app.debug = True
app.secret_key = urandom(32)     # random key each run

request_validator = None
response_validator = None

options_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "1728000",        # 20 days
    "Content-Length": "0"
}


with open(path.join(path.dirname(__file__), "openapi.json"), "r") as openapi:
    spec = create_spec(json.load(openapi))
    request_validator = RequestValidator(spec)
    response_validator = ResponseValidator(spec)


@app.before_request()
def corse_request(req):
    if req.uri.startswith("/p/"):
        return      # enndpoints for printers does not need CORS
    if req.method_number == state.METHOD_OPTIONS:
        res = Response(content_type="text/plain; charset=UTF-8",
                       headers=options_headers,
                       status_code=state.HTTP_NO_CONTENT)
        raise HTTPException(res)


@app.after_request()
def corse_response(req, res):
    res.add_header("Access-Control-Allow-Origin",
                   req.headers.get("Origin", "*"))
    res.add_header("Access-Control-Allow-Credentials", "true")
    return res


@app.before_request()
def before_each_request(req):
    req.api = OpenAPIRequest(req)
    result = request_validator.validate(req.api)
    if result.errors:
        errors = []
        for error in result.errors:
            log.debug(error)
            if isinstance(error, (InvalidOperation, OperationNotFound,
                                  InvalidPath, PathNotFound)):
                return  # not found
            if isinstance(error, InvalidSecurity):
                abort(JSONResponse(error=str(errors), status_code=401,
                                   charset=None))

            errors.append(repr(error)+":"+str(error))
        abort(JSONResponse(error=';'.join(errors), status_code=400,
                           charset=None))


@app.after_request()
def after_each_request(req, res):
    """Check if ansewer is valid by OpenAPI."""
    result = response_validator.validate(
        req.api or OpenAPIRequest(req),     # when error in before_request
        OpenAPIResponse(res))
    for error in result.errors:
        if isinstance(error, InvalidOperation):
            continue
        log.error("API output error: %s", str(error))
    return res


@app.route("/plain_text")
def plain_text(req):
    return "Hello world", "text/plain"


@app.route("/json/<arg>")
def ajax_arg(req, arg):
    return json.dumps({"arg": arg}), "application/json"


@app.route('/json', method=state.METHOD_POST | state.METHOD_PUT)
def test_json(req):
    return JSONResponse(status_code=418, message="I'm teapot :-)",
                        request=req.json)


@app.route("/arg/<int_arg:int>")
def ajax_integer(req, arg):
    return json.dumps({"integer_arg": arg}), "application/json"


@app.route("/arg/<float_arg:float>")
def ajax_float(req, arg):
    return json.dumps({"float_arg": arg}), "application/json"


@app.route('/internal-server-error')
def method_raises_errror(req):
    raise RuntimeError('Test of internal server error')


@app.route('/login')
def login(req):
    cookie = PoorSession(req)
    cookie.data['login'] = True
    response = Response(status_code=204)
    cookie.header(response)
    return response


@app.route('/check/login')
def check_login(req):
    cookie = PoorSession(req)
    if 'login' not in cookie.data:
        raise HTTPException(401)
    return "login ok"


@app.route('/check/api-key')
def check_api_key(req):
    api_token = req.headers.get("API-Key", None)
    if api_token != "xxx":
        raise HTTPException(401)
    return "api-key ok"


@app.http_state(state.HTTP_NOT_FOUND)
def not_found(req):
    return (json.dumps(
        {"error": "Url %s, you are request not found" % req.uri}),
        "application/json", None, 404)


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on 127.0.0.1:8080")
    httpd.serve_forever()
