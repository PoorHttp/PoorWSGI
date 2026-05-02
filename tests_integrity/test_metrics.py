"""Integrity tests for the metrics example."""
# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use

from os import environ
from os.path import dirname, join, pardir

from pytest import fixture

from . support import start_server, check_url


@fixture(scope="module")
def url(request):
    """Returns the server URL or starts the metrics application if it doesn't
    exist."""
    process = None
    retval = environ.get("TEST_METRICS_URL", "").rstrip('/')
    if retval:
        yield retval
    else:
        process = start_server(
            request,
            join(dirname(__file__), pardir, 'examples/metrics.py'))
        yield "http://localhost:8080"  # server is running

    if process is not None:
        process.kill()
        process.wait()


class TestMetrics():
    """Tests for example endpoints."""
    def test_root(self, url):
        """Tests the root endpoint."""
        res = check_url(url+"/",
                        headers={'Accept': 'text/plain'})
        assert res.headers["Content-Type"] == "text/plain"

    def test_metrics(self, url):
        """Tests the metrics endpoint."""
        res = check_url(url+"/metrics")
        assert res.headers["Content-Type"].startswith("application/json")

    def test_invalid_request(self, url):
        """Tests an invalid request to an endpoint."""
        check_url(url+"/json", status_code=400,
                  method="POST", data={'message': 'invalid'},
                  headers={'Content-Type': 'application/json'})
