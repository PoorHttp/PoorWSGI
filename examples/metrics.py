"""Metrics example."""
from wsgiref.simple_server import make_server
from time import time
from sys import path as python_path

import os

EXAMPLES_PATH = os.path.dirname(__file__)
python_path.insert(0, os.path.abspath(
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.response import JSONResponse  # noqa

app = application = Application('metrics')


class Metrics:
    """Simple metrics class."""
    requests = 0
    response_time = 0
    best_time = float('inf')
    worst_time = 0

    @staticmethod
    def avg():
        """Return average response time."""
        if Metrics.requests:
            return Metrics.response_time / Metrics.requests
        return 0

    @staticmethod
    def measure(start_time):
        """Do measure."""
        Metrics.requests += 1
        response_time = time() - start_time
        Metrics.response_time += response_time
        Metrics.best_time = min(Metrics.best_time, response_time)
        Metrics.worst_time = max(Metrics.worst_time, response_time)


@app.after_response()
def metrics_end(req, res):
    """End measuring response time."""
    Metrics.measure(req.start_time)
    return res


@app.route('/metrics')
def metrics(req):
    """Return response metrics:"""
    assert req
    return JSONResponse(
        requests=Metrics.requests,
        avg_time=Metrics.avg(),
        best_time=Metrics.best_time,
        worst_time=Metrics.worst_time)


@app.route('/')
def root(req):
    """Simple hello world response."""
    assert req
    return "Hello World", "text/plain"


@app.route('/json', method=state.METHOD_POST)
def test_json(req):
    """Simple POST method."""
    return JSONResponse(status_code=418, message="I'm teapot :-)",
                        request=req.json)


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
