"""HTTP Authenticate Digest method.

This file could be used as known ``htdigest`` tool.

.. code ::sh

    python3 -m poorwsgi.digest --help

    # adding / updating user password
    python3 -m poorwsgi.digest -c auth.digest 'Secret Zone' user
"""
from argparse import ArgumentParser
from hashlib import md5, sha256
from traceback import print_exc
from getpass import getpass
from os.path import exists
from logging import getLogger
from functools import wraps
from collections import defaultdict

import sys

from poorwsgi import state
from poorwsgi.response import HTTPException
from poorwsgi.session import check_token

log = getLogger("poorwsgi")  # pylint: disable=invalid-name


def check_response(req, password):
    """Check digest response value.

    Return True if response value is right.
    """

    kwargs = req.authorization.copy()
    kwargs['hash1'] = password

    # session algorithm support
    if req.app.auth_algorithm.endswith('-sess'):
        hash1 = req.app.auth_hash(
            "{hash1}:{nonce}:{cnonce}".format(**kwargs).encode()).hexdigest()
        kwargs['hash1'] = hash1

    kwargs['method'] = req.method

    hash2 = req.app.auth_hash(
        '{method}:{uri}'.format(**kwargs).encode()
        ).hexdigest()
    # auth-int support XXX: not tested
    # md5_body = algorithm(req.data.encode()).hexdigest()
    # hash2 = algorithm(
    #     '{req.method}:{uri}:{md5_body}'
    #     ''.format(req=req, md5_body=md5_body).encode()
    #     ).hexdigest()
    kwargs['hash2'] = hash2

    # auth qop
    if req.app.auth_qop:
        # pylint: disable=fixme
        # TODO: check nc value on server side
        response = req.app.auth_hash(
            '{hash1}:{nonce}:{nc}:{cnonce}:{qop}:{hash2}'
            ''.format(**kwargs).encode()).hexdigest()
    else:
        response = req.app.auth_hash(
            '{hash1}:{nonce}:{hash2}'
            ''.format(**kwargs).encode()).hexdigest()
    return response == kwargs['response']


def check_credentials(req, realm, username=None):
    """Check Digest authorization credentials.

    Return True if Authorization header is valid for realm.
    Username is checked too, if it is set.
    """
    # pylint: disable=too-many-return-statements

    app = req.app
    auth = req.authorization
    opaque = sha256(req.server_hostname.encode()).hexdigest()

    if auth.get("algorithm") != app.auth_algorithm:
        log.error('Digest: algorithm %s not equal to %s',
                  auth.get("algorithm"), app.auth_algorithm)
        return False

    if auth.get('opaque') != opaque:
        log.error('Digest: opaque %s not equal to %s',
                  auth.get('opaque'), opaque)
        return False

    if not auth.get('uri').endswith(req.full_path):
        log.error('Digest: uri %s not equal to %s',
                  auth.get('uri'), req.full_path)
        return False

    if app.auth_qop and auth.get('qop') != app.auth_qop:
        log.error('Digest: qop %s not equal to %s',
                  auth.get('qop'), app.auth_qop)
        return False

    if auth.get('realm') != realm:
        log.error('Digest: realm %s not equal to %s',
                  auth.get('realm'), realm)
        return False

    if username and auth.get('username') != username:
        log.error('Digest: username not match.')
        return False

    if 'response' not in auth:
        log.error('Digest: response value not found')
        return False

    password = app.auth_map.get(realm, {}).get(auth.get('username'))
    if not password:
        log.error('Digest: username not found in auth_map')
        return False

    if not check_response(req, password):
        log.error('Digest: response not match')
        return False
    return True


def check_digest(realm, username=None):
    """Check HTTP Digest Authenticate.

    Allow only valid HTTP Digest authorization for realm. Username
    is checked too, if it is set. When no, HTTP_UNAUTHORIZED response was
    raised with realm and stale value if is need.

    When user is valid, req.user attribute is set to username.

    .. code :: python

        app.auth_type = 'Digest'

        @app.route('/admin')
        @check_digest('Admin Zone')
        def admin_zone(req):
            return "This is only for Admins, just like you %s." % req.user


        @app.route('/user-looser')
        @check_digest('Users', looser)
        def looser_only(req):
            return "You are the right looser user."
    """
    def wrapper(fun):
        @wraps(fun)
        def handler(req):
            if 'Authorization' not in req.headers:
                log.info('Digest: Authorization header not found')
                raise HTTPException(state.HTTP_UNAUTHORIZED, realm=realm)

            if req.authorization['type'] != 'Digest':
                log.error('Digest: Bad Authorization type')
                raise HTTPException(state.HTTP_UNAUTHORIZED, realm=realm)

            if not check_token(req.authorization.get('nonce'),
                               req.secret_key, req.user_agent,
                               timeout=req.app.auth_timeout):
                log.info("Digest: nonce value not match")
                raise HTTPException(state.HTTP_UNAUTHORIZED, realm=realm,
                                    stale=True)

            if not check_credentials(req, realm, username):
                raise HTTPException(state.HTTP_UNAUTHORIZED, realm=realm)

            req.user = req.authorization['username']
            return fun(req)
        return handler
    return wrapper


def hexdigest(username, realm, password, algorithm=md5):
    """Return digest hash value for user password.

    Return algorithm(username:realm:password).hexdigest()
    """
    return algorithm(
        ('%s:%s:%s' % (username, realm, password)).encode()
        ).hexdigest()


class PasswordMap(defaultdict):
    """Simple memory object to store user password.

    Attributes:
        pathname : str
            Full path to password file, must be set for PasswordMap.write
            and PasswordMap.load methods.
    """
    def __init__(self, pathname=None):
        super().__init__(dict)
        self.pathname = pathname

    def set(self, realm, username, digest):
        """Add username to realm."""
        self[realm][username] = digest

    def delete(self, realm, username):
        """Delete username from realm."""
        return bool(self[realm].pop(username, None))

    def find(self, realm, username):
        """Return digest for username in realm if exist."""
        if realm in self and username in self[realm]:
            return self[realm][username]
        return None

    def verify(self, realm, username, digest):
        """Check digest in password map."""
        digest_ = self.find(realm, username)
        return bool(digest_) and digest_ == digest

    def load(self):
        """Load map from file."""
        if self.pathname is None:
            raise RuntimeError("No pathname was set.")

        with open(self.pathname) as pwfile:
            for line in pwfile:
                username, realm, digest = line.strip().split(':')
                self.set(realm, username, digest)

    def write(self):
        """Write memory map dump."""
        if self.pathname is None:
            raise RuntimeError("No pathname was set.")

        with open(self.pathname, 'w+') as pwfile:
            for realm, vals in self.items():
                for username, digest in vals.items():
                    pwfile.write('%s:%s:%s\n' % (username, realm, digest))


def get_re_type():
    """Get password from stdin with re-type ."""
    password = getpass('New password: ')
    re_type = getpass('Re-type new password: ')
    if password != re_type:
        print('They don\'t match, sorry.')
        return None
    return password


def main():
    """Main function for manipulation with passwordfile."""
    # pylint: disable=too-many-return-statements
    # pylint: disable=too-many-statements
    # pylint: disable=too-many-branches

    parser = ArgumentParser(
        description="Password file manipulation for digest authenticate"
                    " method.")

    parser.add_argument(
        "passwordfile", type=str, nargs='?',
        help="password file which will be processed")
    parser.add_argument(
        "realm", type=str,
        help="realm string for Authenticate header")
    parser.add_argument(
        "username", type=str,
        help="username string for Authenticate header")
    parser.add_argument(
        "-c", action="store_true",
        help="create a new file")
    parser.add_argument(
        "-n", action="store_true",
        help="don't update file, display results on stdout")
    parser.add_argument(
        "-m", action="store_true",
        help="force MD5 encryption of the password (default)")
    parser.add_argument(
        "-s", action="store_true",
        help="force SHA-256 encryption of the password")
    parser.add_argument(
        "-D", action="store_true",
        help="delete specified user")
    parser.add_argument(
        "-v", action="store_true",
        help="verify password for the specified user")

    parser.add_argument(
        "--version", action="version",
        version="PoorWSGI %s %s." % (parser.prog, state.__version__))

    args = parser.parse_args()
    algorithm = md5
    if args.s and not args.m:
        algorithm = sha256

    try:
        if args.n:
            password = get_re_type()
            if password is None:
                return 1
            digest = hexdigest(args.username, args.realm, password)
            print('%s:%s:%s' % (args.username, args.realm, digest))
            return 0

        if not args.passwordfile:
            parser.error('Password file argument is required.')
            return 1

        passwordfile = PasswordMap(args.passwordfile)
        if not exists(args.passwordfile):
            if (args.v or args.D) or not args.c:
                parser.error('Password file not found.')
                return 1
        else:
            passwordfile.load()

        if args.v:
            password = getpass('Password: ')
            digest = hexdigest(args.username, args.realm, password, algorithm)
            if passwordfile.verify(args.realm, args.username, digest):
                print('Valid user.')
                return 0
            print('Invalid user.')
            return 2

        # modify password file
        if args.D:
            if passwordfile.delete(args.realm, args.username):
                print('User `%s` was be deleted.' % args.username)
            else:
                print('User `%s` not found.' % args.username)
        else:
            if passwordfile.find(args.realm, args.username):
                print('Changing password for user `%s` in realm `%s`.' %
                      (args.username, args.realm))
            else:
                print('Adding user `%s` in realm `%s`.' %
                      (args.username, args.realm))

            password = get_re_type()
            if password is None:
                return 1

            digest = hexdigest(args.username, args.realm, password, algorithm)
            passwordfile.set(args.realm, args.username, digest)

        passwordfile.write()

        return 0
    except Exception as err:  # pylint: disable=broad-except
        print_exc(file=sys.stderr)
        parser.error(str(err))


if __name__ == "__main__":
    sys.exit(main())
