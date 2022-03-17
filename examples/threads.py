"""Threads and fast response example.

.. code :: bash

    uwsgi --plugin python3 --http-socket localhost:8080 --wsgi-file threads.py

"""

from wsgiref.simple_server import WSGIServer, make_server
from socketserver import ThreadingMixIn
from sys import path as python_path
from time import sleep

import os

EXAMPLES_PATH = os.path.dirname(__file__)           # noqa
python_path.insert(0, os.path.abspath(              # noqa
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

from poorwsgi import Application, state
from poorwsgi.response import EmptyResponse, JSONResponse

app = application = Application("threading")


@app.after_response()
def after_response(req, res):
    """Process response"""
    assert req
    print("Request:", str(req.headers), req.data)
    print("Response (%s):" % res.content_type, res.data)
    if res.data:
        sleep(0.2)
    return res


@app.route('/empty')
def empty(req):
    """Return empty response."""
    assert req
    return EmptyResponse()


@app.route('/hello_world')
def hello_world(req):
    """Return empty response."""
    assert req
    return "Hello World!"

@app.route('/json-response', method=state.METHOD_POST)
def json_response(req):
    """Return json response"""
    assert req
    return JSONResponse(status_code=400, code='MESSAGE', message='Message')


class Mini():

    def __call__(self, env, start_response):
        start_response("200 OK", [])
        return ()


class ThreadingServer(ThreadingMixIn, WSGIServer):
    """WSGIServer which run request in thread."""
    daemon_threads = True


mini = Mini()

if __name__ == '__main__':

    httpd = make_server('127.0.0.1', 8080, app, server_class=ThreadingServer)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
