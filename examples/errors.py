"""Error handling example."""
from wsgiref.simple_server import make_server
from sys import path as python_path

import os
import logging as log

EXAMPLES_PATH = os.path.dirname(__file__)
python_path.insert(0, os.path.abspath(
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

from poorwsgi import Application, state  # noqa
from poorwsgi.response import HTTPException, Response, make_response

logger = log.getLogger()
logger.setLevel("DEBUG")
app = application = Application("simple")
app.debug = True



@app.http_state(400)
def bad_request_handler(req, error=None):
    """Bad Request handler"""
    assert req
    log.error("error: %s", error)
    return  Response("Bad Request", content_type="text/plain", status_code=400)


@app.http_state(411)
def length_required_handler(req, error=None):
    """Bad request handler"""
    assert req
    if error:
        log.error("%s", error)
    return make_response("length required", status_code=411)


@app.route('/')
def root(req):
    """Return root"""
    assert req
    return 'Hello world!', "text/plain"


@app.route('/bad_request')
def bad_request(req):
    """Raise Bad Request exception"""
    raise HTTPException(state.HTTP_BAD_REQUEST, error="poslal si to špatně")


@app.route('/length_required')
def length_required(req):
    """Raise Length Required exception"""
    assert req
    raise HTTPException(state.HTTP_LENGTH_REQUIRED,
                        error="Missing content length or no content")




if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
