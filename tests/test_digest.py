"""Tests for digest functionality."""
from collections import defaultdict
from os.path import dirname, join, pardir

from pytest import fixture

from poorwsgi import Application
from poorwsgi.digest import PasswordMap, hexdigest
from poorwsgi.request import Request

FILE = join(dirname(__file__), pardir, "examples/test.digest")
REALM = 'User Zone'
USER = 'user'
DIGEST = '99f490dffe2c74a7f13d0cf9b61098a5'  # looser
HEADER = '''
    Digest username="user", realm="User Zone",
    nonce="1bcb61aa4910f2d462db474efd51a49018413d811536d746538715480e7e730a",
    uri="/user", algorithm=MD5-sess,
    response="0dcecfef979808a940c34af8a3bc7ee4",
    opaque="5af87f1f655f3e60b744462318d3bbcaae8079df107dbcb08168e1a93fd943d0",
    qop=auth, nc=00000002, cnonce="b636b6204f836fdc"'''
DICT = {  # Dictionary from HEADER values
    "type": 'Digest',
    "username": 'user',
    "realm": 'User Zone',
    "nonce":
    '1bcb61aa4910f2d462db474efd51a49018413d811536d746538715480e7e730a',
    "uri": '/user',
    "algorithm": 'MD5-sess',
    "response": '0dcecfef979808a940c34af8a3bc7ee4',
    "opaque":
    '5af87f1f655f3e60b744462318d3bbcaae8079df107dbcb08168e1a93fd943d0',
    "qop": 'auth',
    "nc": '00000002',
    "cnonce": 'b636b6204f836fdc'
}

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use
# pylint: disable=redefined-outer-name


@fixture
def pmap():
    obj = PasswordMap()
    obj.set(REALM, USER, DIGEST)
    return obj


@fixture(scope='session')
def app():
    return Application(__name__)


@fixture
def req(app):
    env = defaultdict(str)
    env['PATH_INFO'] = '/user'
    env['HTTP_AUTHORIZATION'] = HEADER
    req = Request(env, app)
    return req


class TestMap():
    """Test for PasswordMap class."""

    def test_set(self, pmap):
        assert REALM in pmap
        assert USER in pmap[REALM]
        assert pmap[REALM][USER] == DIGEST

    def test_delete(self, pmap):
        assert pmap.delete(REALM, USER) is True
        assert pmap.delete(REALM, USER) is False

    def test_find(self, pmap):
        assert pmap.find(REALM, USER) == DIGEST
        assert pmap.find('', USER) is None
        assert pmap.find(REALM, '') is None

    def test_verify(self, pmap):
        assert pmap.verify(REALM, USER, DIGEST) is True
        assert pmap.verify(REALM, USER, '') is False
        assert pmap.verify(REALM, '', DIGEST) is False
        assert pmap.verify('', USER, DIGEST) is False

    def test_load(self):
        pmap = PasswordMap(FILE)
        pmap.load()
        assert pmap.verify(REALM, USER, DIGEST) is True


def test_hexdigest():
    assert hexdigest(USER, REALM, 'looser') == DIGEST


def test_header_parsing(req):
    assert req.authorization == DICT
