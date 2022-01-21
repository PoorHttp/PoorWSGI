"""Integrity test for metrics example."""
# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use

from os import environ
from os.path import dirname, join, pardir

from pytest import fixture

from . support import start_server, check_url


@fixture(scope="module")
def url(request):
    """Return server url or if exists or start metrics application."""
    retval = environ.get("TEST_METRICS_URL", "").strip('/')
    if retval:
        yield retval
        return

    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/metrics.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()


class TestMetrics():
    """Tests for example endpoints."""
    def test_root(self, url):
        res = check_url(url+"/",
                        headers={'Accept': 'text/plain'})
        assert res.headers["Content-Type"] == "text/plain"

    def test_metrics(self, url):
        res = check_url(url+"/metrics")
        assert res.headers["Content-Type"].startswith("application/json")

    def test_invalid_request(self, url):
        check_url(url+"/json", status_code=400,
                  method="POST", data={'message': 'invalid'},
                  headers={'Content-Type': 'application/json'})
