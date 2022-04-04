"""HTTP Digest example test."""
from os import environ
from os.path import dirname, join, pardir

from requests.auth import HTTPDigestAuth
from pytest import fixture, mark

from . support import start_server, check_url

# pylint: disable=inconsistent-return-statements
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use


@fixture(scope="module")
def url(request):
    """URL (server fixture in fact)."""
    val = environ.get("TEST_DIGEST_URL", "").strip('/')
    if val:
        return val

    process = start_server(
        request,
        join(dirname(__file__), pardir, 'examples/http_digest.py'))

    yield "http://localhost:8080"  # server is running
    process.kill()


@fixture
def admin_auth():
    return HTTPDigestAuth('admin', 'admin')


@fixture
def user_auth():
    return HTTPDigestAuth('user', 'looser')


@fixture
def utf8_auth():
    return HTTPDigestAuth('Ondřej', 'heslíčko')


class TestDigest:
    """Test http_digest example."""
    def test_unauthorized(self, url):
        check_url(url+'/admin_zone', status_code=401)
        check_url(url+'/user_zone', status_code=401)
        check_url(url+'/user', status_code=401)
        check_url(url+'/foo/passwd', method='POST', status_code=401, data={})

    def test_admin(self, url, admin_auth):
        check_url(url+'/admin_zone', auth=admin_auth)
        check_url(url+'/admin_zone', params=dict(arg=42), auth=admin_auth)

    def test_user(self, url, user_auth):
        check_url(url+'/user_zone', auth=user_auth)
        check_url(url+'/user_zone', params=dict(param='text'), auth=user_auth)
        check_url(url+'/user', auth=user_auth)

    @mark.skip("https://github.com/psf/requests/issues/6102")
    def test_utf8(self, url, utf8_auth):
        """Check UTF-8 characters in username."""
        check_url(url+'/user/utf-8', auth=utf8_auth)
        check_url(url+'/user/utf-8', params=dict(param='text'), auth=utf8_auth)

    def test_foo(self, url):
        auth = HTTPDigestAuth('foo', 'bar')
        check_url(url+'/foo', params=dict(x=123), auth=auth)
        check_url(url+'/foo', auth=auth)

        check_url(url+'/foo/passwd', method='POST', auth=auth,
                  data={'password': 'rab'},
                  allow_redirects=False, status_code=302)

        auth = HTTPDigestAuth('foo', 'rab')
        check_url(url+'/foo', auth=auth)

    def test_spaces(self, url, user_auth):
        check_url(url+'/spaces%20in%20url', auth=user_auth)

    def test_diacritics(self, url, user_auth):
        check_url(url+'/%C4%8De%C5%A1tina%20v%20url', auth=user_auth)

    def test_unicode_smile(self, url, user_auth):
        check_url(url+'/crazy%20in%20url%20%F0%9F%A4%AA', auth=user_auth)

    def test_unknown(self, url, user_auth):
        check_url(url+'/unknown', auth=user_auth, status_code=401)
