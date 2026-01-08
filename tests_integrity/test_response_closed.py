"""Integrity test for closed buffer handling."""
from os.path import dirname, join, pardir

from pytest import fixture
from requests import Session

from .support import check_url, start_server

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name


@fixture(scope="module")
def url(request):
    """URL (server fixture in fact)."""
    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/response_closed.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()
    process.wait()


class TestResponseClosed:
    """Test for Response with closed buffer handling."""

    def test_simple_response(self, url):
        """Test that a simple response works normally."""
        check_url(url+"/test")

    def test_response_data_access(self, url):
        """Test that accessing data property before sending works."""
        check_url(url+"/test-after-response")
