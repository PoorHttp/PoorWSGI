"""HTTP Digest example test."""
from os import environ
from os.path import dirname, join, pardir

from pytest import fixture, mark
from requests.auth import HTTPDigestAuth

from .support import check_url, start_server

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use


@fixture(scope="module")
def url(request):
    """The URL (server fixture)."""
    process = None
    val = environ.get("TEST_DIGEST_URL", "").rstrip('/')
    if val:
        yield val
    else:
        process = start_server(
            request,
            join(dirname(__file__), pardir, 'examples/http_digest.py'))
        yield "http://localhost:8080"  # server is running

    if process is not None:
        process.kill()
        process.wait()


@fixture
def admin_auth():
    """Fixture for admin authentication."""
    return HTTPDigestAuth('admin', 'admin')


@fixture
def user_auth():
    """Fixture for user authentication."""
    return HTTPDigestAuth('user', 'looser')


@fixture
def utf8_auth():
    """Fixture for UTF-8 user authentication."""
    return HTTPDigestAuth('Ondřej', 'heslíčko')


class TestDigest:
    """Tests the http_digest example."""

    def test_unauthorized(self, url):
        """Tests unauthorized access to various endpoints."""
        check_url(url+'/admin_zone', status_code=401)
        check_url(url+'/user_zone', status_code=401)
        check_url(url+'/user', status_code=401)
        check_url(url+'/foo/passwd', method='POST', status_code=401, data={})

    def test_admin(self, url, admin_auth):
        """Tests access to the admin zone with admin credentials."""
        check_url(url+'/admin_zone', auth=admin_auth)
        check_url(url+'/admin_zone', params={"arg": 42}, auth=admin_auth)

    def test_user(self, url, user_auth):
        """Tests access to the user zone with user credentials."""
        check_url(url+'/user_zone', auth=user_auth)
        check_url(url+'/user_zone', params={"param": 'text'}, auth=user_auth)
        check_url(url+'/user', auth=user_auth)

    @mark.skip("https://github.com/psf/requests/issues/6102")
    def test_utf8(self, url, utf8_auth):
        """Checks UTF-8 characters in the username."""
        check_url(url+'/user/utf-8', auth=utf8_auth)
        check_url(url+'/user/utf-8', params={"param": 'text'}, auth=utf8_auth)

    def test_foo(self, url):
        """Tests changing the password for the 'foo' user."""
        auth = HTTPDigestAuth('foo', 'bar')
        check_url(url+'/foo', params={"x": 123}, auth=auth)
        check_url(url+'/foo', auth=auth)

        check_url(url+'/foo/passwd', method='POST', auth=auth,
                  data={'password': 'rab'},
                  allow_redirects=False, status_code=302)

        auth = HTTPDigestAuth('foo', 'rab')
        check_url(url+'/foo', auth=auth)

    def test_spaces(self, url, user_auth):
        """Tests URLs with spaces in the path."""
        check_url(url+'/spaces%20in%20url', auth=user_auth)

    def test_diacritics(self, url, user_auth):
        """Tests URLs with diacritics in the path."""
        check_url(url+'/%C4%8De%C5%A1tina%20v%20url', auth=user_auth)

    def test_unicode_smile(self, url, user_auth):
        """Tests URLs with Unicode smileys in the path."""
        check_url(url+'/crazy%20in%20url%20%F0%9F%A4%AA', auth=user_auth)

    def test_unknown(self, url, user_auth):
        """Tests access to an unknown endpoint."""
        check_url(url+'/unknown', auth=user_auth, status_code=401)
