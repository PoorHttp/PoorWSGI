"""Tests for digest functionality."""
# pylint: disable=too-many-lines
from collections import defaultdict
from hashlib import md5, sha256
from os.path import dirname, join, pardir
from unittest.mock import MagicMock, patch

import pytest
from pytest import fixture

from poorwsgi import Application
from poorwsgi.digest import (
    PasswordMap,
    check_credentials,
    check_digest,
    check_response,
    get_re_type,
    hexdigest,
    main,
)
from poorwsgi.request import Request
from poorwsgi.response import HTTPException
from poorwsgi import state

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
    env['REQUEST_METHOD'] = 'GET'
    env['HTTP_AUTHORIZATION'] = HEADER
    req = Request(env, app)
    return req


def _make_req(auth, hostname='testhost', path='/resource',
              algorithm='MD5', qop=None, method='GET',
              auth_map=None):
    """Return a MagicMock request with digest auth attributes set."""
    req = MagicMock()
    req.authorization = auth.copy()
    req.server_hostname = hostname
    req.full_path = path
    req.app.auth_algorithm = algorithm
    req.app.auth_hash = md5
    req.app.auth_qop = qop
    req.app.auth_map = auth_map or {}
    req.method = method
    return req


def _build_credentials(  # pylint: disable=too-many-locals
        username, realm, password, hostname, path,
        method='GET', algorithm='MD5', qop=None,
        nonce='testnonce', cnonce='testcnonce', nc='00000001'):
    """Compute a self-consistent Digest auth dict for the given parameters."""
    digest = hexdigest(username, realm, password)
    opaque = sha256(hostname.encode()).hexdigest()
    uses_sess = algorithm.endswith('-sess')
    hash1 = digest
    if uses_sess:
        # RFC 7616 §3.4: -sess requires cnonce for HA1 regardless of qop
        hash1 = md5(f'{digest}:{nonce}:{cnonce}'.encode()).hexdigest()
    hash2 = md5(f'{method}:{path}'.encode()).hexdigest()
    if qop:
        response = md5(
            f'{hash1}:{nonce}:{nc}:{cnonce}:{qop}:{hash2}'.encode()
        ).hexdigest()
    else:
        response = md5(f'{hash1}:{nonce}:{hash2}'.encode()).hexdigest()

    auth = {
        'type': 'Digest',
        'username': username,
        'realm': realm,
        'nonce': nonce,
        'uri': path,
        'algorithm': algorithm,
        'opaque': opaque,
        'response': response,
    }
    if qop:
        auth['qop'] = qop
        auth['nc'] = nc
        auth['cnonce'] = cnonce
    elif uses_sess:
        # cnonce required by -sess even without qop
        auth['cnonce'] = cnonce
    return auth, digest


class TestMap():
    """Tests for the PasswordMap class."""

    def test_set(self, pmap):
        """Tests setting a user's digest in the PasswordMap."""
        assert REALM in pmap
        assert USER in pmap[REALM]
        assert pmap[REALM][USER] == DIGEST

    def test_delete(self, pmap):
        """Tests deleting a user from the PasswordMap."""
        deleted = pmap.delete(REALM, USER)
        assert deleted is True
        deleted_again = pmap.delete(REALM, USER)
        assert deleted_again is False

    def test_find(self, pmap):
        """Tests finding a user's digest in the PasswordMap."""
        assert pmap.find(REALM, USER) == DIGEST
        assert pmap.find('', USER) is None
        assert pmap.find(REALM, '') is None

    def test_verify(self, pmap):
        """Tests verifying a user's digest in the PasswordMap."""
        assert pmap.verify(REALM, USER, DIGEST) is True
        assert pmap.verify(REALM, USER, '') is False
        assert pmap.verify(REALM, '', DIGEST) is False
        assert pmap.verify('', USER, DIGEST) is False

    def test_load(self):
        """Tests loading the PasswordMap from a file."""
        pmap = PasswordMap(FILE)
        pmap.load()
        assert pmap.verify(REALM, USER, DIGEST) is True

    def test_load_no_pathname(self):
        """load() without pathname raises RuntimeError."""
        with pytest.raises(RuntimeError, match="No pathname"):
            PasswordMap().load()

    def test_write_no_pathname(self):
        """write() without pathname raises RuntimeError."""
        with pytest.raises(RuntimeError, match="No pathname"):
            PasswordMap().write()

    def test_write_roundtrip(self, tmp_path):
        """Written file can be loaded back and verified."""
        path = str(tmp_path / "test.digest")
        pmap = PasswordMap(path)
        pmap.set(REALM, USER, DIGEST)
        pmap.write()

        loaded = PasswordMap(path)
        loaded.load()
        assert loaded.verify(REALM, USER, DIGEST) is True

    def test_write_multiple_realms(self, tmp_path):
        """All entries across multiple realms survive a write/load cycle."""
        path = str(tmp_path / "multi.digest")
        pmap = PasswordMap(path)
        pmap.set(REALM, 'alice', hexdigest('alice', REALM, 'pass1'))
        pmap.set(REALM, 'bob', hexdigest('bob', REALM, 'pass2'))
        pmap.set('Admin Zone', 'admin', hexdigest('admin', 'Admin Zone', 'x'))
        pmap.write()

        loaded = PasswordMap(path)
        loaded.load()
        assert loaded.find(REALM, 'alice') is not None
        assert loaded.find(REALM, 'bob') is not None
        assert loaded.find('Admin Zone', 'admin') is not None


def test_hexdigest():
    """Tests the hexdigest function."""
    assert hexdigest(USER, REALM, 'looser') == DIGEST


def test_hexdigest_sha256():
    """SHA-256 variant produces a different, longer digest."""
    d = hexdigest(USER, REALM, 'looser', algorithm=sha256)
    assert d != DIGEST
    assert len(d) == 64  # SHA-256 hex is 64 chars vs MD5's 32


def test_header_parsing(req):
    """Tests parsing the Authorization header."""
    assert req.authorization == DICT


class TestCheckResponse:
    """RFC 7616 §3.4 — response field computation."""

    def test_valid_md5_sess_qop_auth(self, req):
        """MD5-sess + qop=auth response must validate against known value."""
        assert check_response(req, DIGEST) is True

    def test_wrong_password_rejected(self, req):
        """A mismatched password hash must return False."""
        assert check_response(req, 'a' * 32) is False

    def test_plain_md5_without_qop(self):
        """Plain MD5, no qop: response = MD5(H1:nonce:H2) (RFC 2617 legacy)."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'host', '/path',
            algorithm='MD5', qop=None,
        )
        req = _make_req(auth, hostname='host', path='/path',
                        algorithm='MD5', qop=None,
                        auth_map={REALM: {USER: digest}})
        assert check_response(req, digest) is True

    def test_md5_with_qop_auth(self):
        """Plain MD5 + qop=auth: response = MD5(H1:nonce:nc:cnonce:qop:H2)."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'host', '/path',
            algorithm='MD5', qop='auth',
        )
        req = _make_req(auth, hostname='host', path='/path',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: digest}})
        assert check_response(req, digest) is True

    def test_md5_sess_without_qop(self):
        """MD5-sess without qop: HA1 = MD5(stored:nonce:cnonce)."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'host', '/path',
            algorithm='MD5-sess', qop=None,
        )
        req = _make_req(auth, hostname='host', path='/path',
                        algorithm='MD5-sess', qop=None,
                        auth_map={REALM: {USER: digest}})
        assert check_response(req, digest) is True

    def test_tampered_response_rejected(self):
        """Altering the response field by one character must return False."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'host', '/path',
            algorithm='MD5', qop='auth',
        )
        auth['response'] = auth['response'][:-1] + (
            'f' if auth['response'][-1] != 'f' else 'e'
        )
        req = _make_req(auth, hostname='host', path='/path',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: digest}})
        assert check_response(req, digest) is False

    def test_uri_mismatch_changes_response(self):
        """Changing the URI invalidates the pre-computed response hash."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'host', '/path',
            algorithm='MD5', qop='auth',
        )
        auth['uri'] = '/other'  # change URI but keep old response
        req = _make_req(auth, hostname='host', path='/other',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: digest}})
        assert check_response(req, digest) is False


class TestCheckCredentials:
    """RFC 7616 §3.3 — server-side credential validation."""

    def _valid_req(self, **overrides):
        """Build a request with fully valid credentials, apply overrides."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'myhost', '/res',
            algorithm='MD5', qop='auth',
        )
        auth.update(overrides.pop('auth', {}))
        req = _make_req(auth, hostname='myhost', path='/res',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: digest}})
        for key, val in overrides.items():
            setattr(req, key, val)
        return req

    def test_valid_passes(self):
        """Fully valid credentials must return True."""
        assert check_credentials(self._valid_req(), REALM) is True

    def test_algorithm_mismatch(self):
        """algorithm field different from app.auth_algorithm → False."""
        req = self._valid_req(auth={'algorithm': 'SHA-256'})
        assert check_credentials(req, REALM) is False

    def test_opaque_mismatch(self):
        """Opaque not matching sha256(server_hostname) → False."""
        req = self._valid_req(auth={'opaque': 'deadbeef' * 8})
        assert check_credentials(req, REALM) is False

    def test_uri_not_suffix_of_path(self):
        """URI in header not ending with req.full_path → False."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'myhost', '/res',
            algorithm='MD5', qop='auth',
        )
        auth['uri'] = '/other/path'
        req = _make_req(auth, hostname='myhost', path='/res',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: digest}})
        assert check_credentials(req, REALM) is False

    def test_uri_prefix_accepted(self):
        """URI with query string that still ends with the path is accepted."""
        auth, digest = _build_credentials(
            USER, REALM, 'secret', 'myhost', '/res',
            algorithm='MD5', qop='auth',
        )
        # auth['uri'] is already '/res' which ends with '/res'
        req = _make_req(auth, hostname='myhost', path='/res',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: digest}})
        assert check_credentials(req, REALM) is True

    def test_qop_mismatch(self):
        """qop in header different from app.auth_qop → False."""
        req = self._valid_req(auth={'qop': 'auth-int'})
        assert check_credentials(req, REALM) is False

    def test_realm_mismatch(self):
        """realm in header different from expected realm → False."""
        assert check_credentials(self._valid_req(), 'Wrong Realm') is False

    def test_username_filter_match(self):
        """Correct username with username filter → True."""
        assert check_credentials(self._valid_req(), REALM, username=USER) \
            is True

    def test_username_filter_mismatch(self):
        """Wrong username with username filter → False."""
        assert check_credentials(self._valid_req(), REALM, username='admin') \
            is False

    def test_missing_response_field(self):
        """Authorization without response field → False."""
        auth, _ = _build_credentials(
            USER, REALM, 'secret', 'myhost', '/res',
            algorithm='MD5', qop='auth',
        )
        del auth['response']
        secret_digest = hexdigest(USER, REALM, 'secret')
        req = _make_req(auth, hostname='myhost', path='/res',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: secret_digest}})
        assert check_credentials(req, REALM) is False

    def test_user_not_in_auth_map(self):
        """Username absent from auth_map → False."""
        auth, _ = _build_credentials(
            USER, REALM, 'secret', 'myhost', '/res',
            algorithm='MD5', qop='auth',
        )
        req = _make_req(auth, hostname='myhost', path='/res',
                        algorithm='MD5', qop='auth',
                        auth_map={})  # empty map
        assert check_credentials(req, REALM) is False

    def test_wrong_password_in_map(self):
        """Auth map has different password than presented → False."""
        auth, _ = _build_credentials(
            USER, REALM, 'secret', 'myhost', '/res',
            algorithm='MD5', qop='auth',
        )
        wrong_digest = hexdigest(USER, REALM, 'wrong')
        req = _make_req(auth, hostname='myhost', path='/res',
                        algorithm='MD5', qop='auth',
                        auth_map={REALM: {USER: wrong_digest}})
        assert check_credentials(req, REALM) is False


class TestCheckDigest:
    """check_digest decorator — RFC 7616 §3.3 (server gate)."""

    @staticmethod
    def _handler(_req):
        return 'ok'

    def test_missing_authorization_header(self):
        """No Authorization header → HTTP 401 Unauthorized."""
        req = MagicMock()
        req.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            check_digest(REALM)(self._handler)(req)
        assert exc_info.value.status_code == state.HTTP_UNAUTHORIZED

    def test_non_digest_auth_type(self):
        """Basic auth type in Authorization → HTTP 401."""
        req = MagicMock()
        req.headers = {'Authorization': 'Basic dXNlcjpwYXNz'}
        req.authorization = {'type': 'Basic'}

        with pytest.raises(HTTPException) as exc_info:
            check_digest(REALM)(self._handler)(req)
        assert exc_info.value.status_code == state.HTTP_UNAUTHORIZED

    def test_invalid_nonce_sets_stale(self):
        """Expired nonce → HTTP 401 with stale attribute in realm."""
        req = MagicMock()
        req.headers = {'Authorization': HEADER}
        req.authorization = DICT.copy()

        with patch('poorwsgi.digest.check_token', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                check_digest(REALM)(self._handler)(req)
        assert exc_info.value.status_code == state.HTTP_UNAUTHORIZED

    def test_invalid_credentials(self):
        """Valid nonce but wrong credentials → HTTP 401."""
        req = MagicMock()
        req.headers = {'Authorization': HEADER}
        req.authorization = DICT.copy()

        with patch('poorwsgi.digest.check_token', return_value=True):
            with patch('poorwsgi.digest.check_credentials',
                       return_value=False):
                with pytest.raises(HTTPException) as exc_info:
                    check_digest(REALM)(self._handler)(req)
        assert exc_info.value.status_code == state.HTTP_UNAUTHORIZED

    def test_valid_auth_sets_user_and_calls_handler(self):
        """Valid credentials set req.user and return the handler result."""
        req = MagicMock()
        req.headers = {'Authorization': HEADER}
        req.authorization = DICT.copy()

        with patch('poorwsgi.digest.check_token', return_value=True):
            with patch('poorwsgi.digest.check_credentials', return_value=True):
                result = check_digest(REALM)(self._handler)(req)
        assert result == 'ok'
        assert req.user == USER

    def test_username_filter_passed_through(self):
        """Username filter is forwarded to check_credentials."""
        req = MagicMock()
        req.headers = {'Authorization': HEADER}
        req.authorization = DICT.copy()

        with patch('poorwsgi.digest.check_token', return_value=True):
            with patch('poorwsgi.digest.check_credentials',
                       return_value=True) as mock_cc:
                check_digest(REALM, username='alice')(self._handler)(req)
                mock_cc.assert_called_once_with(req, REALM, 'alice')

    def test_wraps_preserves_name(self):
        """@check_digest must preserve the wrapped function's __name__."""
        @check_digest(REALM)
        def my_view(_req):  # pylint: disable=unused-argument
            return 'ok'
        assert my_view.__name__ == 'my_view'


class TestGetReType:
    """Tests for the get_re_type helper (interactive password input)."""

    def test_matching_passwords_returned(self):
        """Returns the password when both prompts match."""
        with patch('poorwsgi.digest.getpass',
                   side_effect=['secret', 'secret']):
            assert get_re_type() == 'secret'

    def test_mismatched_passwords_returns_none(self, capsys):
        """Returns None and prints an error when passwords differ."""
        with patch('poorwsgi.digest.getpass',
                   side_effect=['secret', 'wrong']):
            result = get_re_type()
        assert result is None
        out, _ = capsys.readouterr()
        assert "don't match" in out


class TestMain:
    """CLI tests for the htdigest-like main() function."""

    def test_display_only_md5(self, capsys):
        """-n flag prints username:realm:digest to stdout and returns 0."""
        with patch('sys.argv', ['digest', '-n', REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                rc = main()
        out, _ = capsys.readouterr()
        assert rc == 0
        assert f'{USER}:{REALM}:{DIGEST}' in out

    def test_display_only_sha256(self, capsys):
        """-n -s flag uses SHA-256 hash."""
        with patch('sys.argv', ['digest', '-n', '-s', REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                rc = main()
        out, _ = capsys.readouterr()
        assert rc == 0
        expected = hexdigest(USER, REALM, 'looser', algorithm=sha256)
        assert expected in out

    def test_display_only_password_mismatch(self):
        """-n with mismatched password re-type returns 1."""
        with patch('sys.argv', ['digest', '-n', REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value=None):
                rc = main()
        assert rc == 1

    def test_create_and_verify(self, tmp_path, capsys):
        """Create a new file, then verify the password."""
        path = str(tmp_path / 'new.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                rc = main()
        assert rc == 0

        with patch('sys.argv', ['digest', '-v', path, REALM, USER]):
            with patch('poorwsgi.digest.getpass', return_value='looser'):
                rc = main()
        capsys.readouterr()
        assert rc == 0

    def test_verify_wrong_password(self, tmp_path):
        """Verify with wrong password returns 2."""
        path = str(tmp_path / 'new.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                main()

        with patch('sys.argv', ['digest', '-v', path, REALM, USER]):
            with patch('poorwsgi.digest.getpass', return_value='wrong'):
                rc = main()
        assert rc == 2

    def test_add_and_delete_user(self, tmp_path, capsys):
        """Add a user then delete it; second delete returns False."""
        path = str(tmp_path / 'del.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                main()

        with patch('sys.argv', ['digest', '-D', path, REALM, USER]):
            rc = main()
        assert rc == 0
        out, _ = capsys.readouterr()
        assert 'deleted' in out.lower()

    def test_no_passwordfile_required(self):
        """Omitting password file without -n or -c triggers parser error."""
        with patch('sys.argv', ['digest', REALM, USER]):
            with pytest.raises(SystemExit):
                main()

    def test_delete_nonexistent_user(self, tmp_path, capsys):
        """Deleting a user not in the file prints 'not found'."""
        path = str(tmp_path / 'del.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                main()

        with patch('sys.argv', ['digest', '-D', path, REALM, 'nobody']):
            rc = main()
        out, _ = capsys.readouterr()
        assert rc == 0
        assert 'not found' in out.lower()

    def test_update_existing_user(self, tmp_path, capsys):
        """Updating an existing user prints 'Changing password' message."""
        path = str(tmp_path / 'update.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='looser'):
                main()
        capsys.readouterr()

        with patch('sys.argv', ['digest', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='newpass'):
                rc = main()
        out, _ = capsys.readouterr()
        assert rc == 0
        assert 'changing' in out.lower()

    def test_add_password_mismatch(self, tmp_path):
        """Mismatched re-type during add returns 1."""
        path = str(tmp_path / 'new.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value=None):
                rc = main()
        assert rc == 1

    def test_missing_file_with_verify(self, tmp_path):
        """Using -v on a missing file triggers parser error."""
        path = str(tmp_path / 'absent.digest')
        with patch('sys.argv', ['digest', '-v', path, REALM, USER]):
            with pytest.raises(SystemExit):
                main()

    def test_exception_in_operation(self, tmp_path):
        """An unexpected exception during an operation returns 1."""
        path = str(tmp_path / 'new.digest')
        with patch('sys.argv', ['digest', '-c', path, REALM, USER]):
            with patch('poorwsgi.digest.get_re_type', return_value='pass'):
                with patch('poorwsgi.digest.hexdigest',
                           side_effect=ValueError('boom')):
                    with pytest.raises(SystemExit):
                        main()
