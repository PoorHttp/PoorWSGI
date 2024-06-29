"""Unit tests for AESSession class."""
from os import urandom
from http.cookies import SimpleCookie

from pytest import fixture, raises

from poorwsgi.aes_session import AESSession
from poorwsgi.session import Session, SessionError

SECRET_KEY = urandom(32)

# pylint: disable=redefined-outer-name
# pylint: disable=no-self-use
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods


@fixture
def session_with_data():
    """AESSession instance with data written into cookie."""
    session = AESSession(SECRET_KEY)
    session.data['test'] = True
    session.write()
    return session


def test_aes_session_is_subclass_of_session():
    """AESSession must inherit from Session."""
    assert issubclass(AESSession, Session)
    assert isinstance(AESSession(SECRET_KEY), Session)


class TestErrors:
    """Test exceptions."""

    def test_empty_secret_key(self):
        with raises(SessionError):
            AESSession(b"")

    def test_empty_string_secret_key(self):
        with raises(SessionError):
            AESSession("")

    def test_bad_session_data(self):
        cookies = SimpleCookie()
        cookies["SESSID"] = "notvalidbase64!!!"
        session = AESSession(SECRET_KEY)
        with raises(SessionError):
            session.load(cookies)

    def test_tampered_signature(self):
        """Cookie with valid structure but wrong HMAC must be rejected."""
        session = AESSession(SECRET_KEY)
        session.data['x'] = 1
        session.write()
        raw = session.cookie["SESSID"].value
        # flip last char of signature part
        parts = raw.rsplit('.', 1)
        last = 'A' if parts[1][-1] != 'A' else 'B'
        tampered = parts[0] + '.' + parts[1][:-1] + last
        cookies = SimpleCookie()
        cookies["SESSID"] = tampered
        new_session = AESSession(SECRET_KEY)
        with raises(SessionError):
            new_session.load(cookies)


class TestLoadWrite:
    """Tests of load and write methods."""

    def test_write_returns_str(self):
        session = AESSession(SECRET_KEY)
        result = session.write()
        assert isinstance(result, str)

    def test_write_load_roundtrip(self, session_with_data):
        new_session = AESSession(SECRET_KEY)
        new_session.load(session_with_data.cookie)
        assert new_session.data == {'test': True}

    def test_nonce_uniqueness(self):
        """Two write() calls for same data must produce different cookies."""
        session = AESSession(SECRET_KEY)
        session.data = {'user': 'alice'}
        raw1 = session.write()
        raw2 = session.write()
        assert raw1 != raw2

    def test_write_load_complex_data(self):
        session = AESSession(SECRET_KEY)
        session.data = {'user': 'alice', 'role': 'admin', 'count': 42}
        session.write()
        new_session = AESSession(SECRET_KEY)
        new_session.load(session.cookie)
        expected = {'user': 'alice', 'role': 'admin', 'count': 42}
        assert new_session.data == expected

    def test_wrong_key_raises(self, session_with_data):
        """Session encrypted with one key cannot be read with another."""
        new_session = AESSession(urandom(32))
        with raises(SessionError):
            new_session.load(session_with_data.cookie)
