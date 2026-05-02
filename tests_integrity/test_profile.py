"""Integrity tests for profiling the JSON test/example application."""
from os import environ
from os.path import dirname, join, pardir

from pytest import fixture

from . support import start_server, check_url

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use
# pylint: disable=consider-using-f-string
# pylint: disable=duplicate-code


@fixture(scope="module")
def server(request):
    """Fixture for starting the profiling JSON example server."""
    process = None
    value = environ.get("TEST_SIMPLE_JSON_URL", "").rstrip('/')
    if value:
        yield value
    else:
        process = start_server(
            request,
            join(dirname(__file__), pardir, 'examples/simple_json.py'),
            {"PROFILE": "1"})
        yield "http://localhost:8080"  # server is running

    if process is not None:
        process.kill()
        process.wait()


class TestRequest:
    """Tests various request attributes related to profiling."""
    # pylint: disable=too-few-public-methods

    def test_profile(self, server):
        """Tests the /profile endpoint."""
        res = check_url(server+"/profile")
        assert res.json()["PROFILE"] == "1"
