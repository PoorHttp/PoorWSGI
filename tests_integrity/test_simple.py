"""Base integrity test"""
from os import environ

from requests import Session
from pytest import fixture

from . support import check_url

URL = environ.get("TEST_SIMPLE_URL", "http://localhost:8080").strip('/')


@fixture
def session():
    session = Session()
    check_url(URL+"/login", status_code=302, session=session,
              allow_redirects=False)
    assert "SESSID" in session.cookies
    return session


class TestSimple():
    def test_root(self):
        check_url(URL)

    def test_static(self):
        check_url(URL+"/test/static")

    def test_variable_int(self):
        check_url(URL+"/test/123")

    def test_variable_float(self):
        check_url(URL+"/test/123.679")

    def test_variable_user(self):
        check_url(URL+"/test/teste@tester.net")

    def test_debug_info(self):
        check_url(URL+"/debug-info")

    def test_404(self):
        check_url(URL+"/no-page", status_code=404)

    def test_500(self):
        check_url(URL+"/internal-server-error", status_code=500)


class TestSession():
    def test_login(self):
        check_url(URL+"/login", status_code=302, allow_redirects=False)

    def test_logout(self, session):
        check_url(URL+"/logout", session=session)
        assert "SESSID" not in session.cookies

    def test_form_get_not_logged(self):
        check_url(URL+"/test/form", status_code=302, allow_redirects=False)

    def test_form_get_logged(self, session):
        check_url(URL+"/test/form", session=session, allow_redirects=False)

    def test_form_post(self, session):
        check_url(URL+"/test/form", method="POST", session=session,
                  allow_redirects=False)

    def test_form_upload(self, session):
        files = {'file_0': ('testfile.py', open(__file__, 'rb'),
                            'text/x-python', {'Expires': '0'})}
        res = check_url(URL+"/test/upload", method="POST", session=session,
                        allow_redirects=False, files=files)
        assert 'testfile.py' in res.text
        assert __doc__ in res.text
        assert 'anything' in res.text
