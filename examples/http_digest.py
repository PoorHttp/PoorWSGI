"""HTTP WWW-Authenticate Digest Example."""
from wsgiref.simple_server import make_server
from sys import path as python_path
from os import path
from hashlib import sha256
from time import time

import logging

python_path.insert(0, path.abspath(              # noqa
    path.join(path.dirname(__file__), path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application, state
from poorwsgi.response import EmptyResponse, redirect
from poorwsgi.digest import check_digest, PasswordMap, hexdigest

FILE = path.join(path.dirname(__file__), 'test.digest')

logging.getLogger().setLevel("DEBUG")
app = application = Application(__name__)  # pylint: disable=invalid-name
# application = app
app.debug = True
app.secret_key = sha256(str(time()).encode()).hexdigest()
# app.auth_algorithm = 'SHA-256-sess'
app.auth_type = 'Digest'
app.auth_timeout = 60

ADMIN = 'Admin Zone'
USER = 'User Zone'
# user/looser, foo/bar, admin/admin
app.auth_map = PasswordMap(FILE)
app.auth_map.load()

# pylint: disable=unused-argument


def get_header(title):
    """Return HTML header list of lines."""
    return (
        "<html>",
        "<head>",
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
        "<title>%s - %s</title>" % (__file__, title),
        "</head>",
        "<body>",
        "<h1>%s - %s</h1>" % (__file__, title)
    )


def get_footer():
    """Return HTML footer list of lines."""
    return (
        "<hr>",
        "<small>Copyright (c) 2020 Ondřej Tůma. See ",
        '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>'
        '</small>.',
        "</body>",
        "</html>"
    )


def get_link(href, text=None, title=None):
    """Return HTML anchor."""
    text = text or title or href
    title = title or text
    return '<a href="%s" title="%s">%s</a>' % (href, title, text)


@app.route('/')
def root(req):
    """Return Root (Index) page."""
    body = (
        '<ul>',
        '<li>%s - admin zone (admin/admin)</li>' % get_link('/admin_zone'),
        '<li>%s - user zone (user/looser)</li>' % get_link('/user_zone'),
        '<li>%s - user (user/looser)</li>' % get_link('/user'),
        '<li>%s - foo (foo/bar)</li>' % get_link('/foo'),
        '<li>%s - unknown</li>' % get_link('/unknown'),
        '</ul>'
    )

    for line in get_header("Root") + body + get_footer():
        yield line.encode()+b'\n'


@app.route('/admin_zone')
@check_digest(ADMIN)
def admin_zone(req):
    """Page only for ADMIN realm."""
    body = (
        '<h2>%s test for %s algorithm.</h2>' % (ADMIN, app.auth_algorithm),
        '<ul>',
        '<li>'+get_link('/', 'Root')+'</li>',
        '<li>'+get_link('/admin_zone?arg=42', 'one more time')+'</li>',
        '</ul>'
    )

    for line in get_header("Root") + body + get_footer():
        yield line.encode()+b'\n'


@app.route('/user_zone')
@check_digest(USER)
def user_zone(req):
    """Page for USER realm."""
    body = (
        '<h2>%s test for %s algorithm.</h2>' % (USER, app.auth_algorithm),
        'User: %s' % req.user,
        '<ul>',
        '<li>'+get_link('/', 'Root')+'</li>',
        '<li>'+get_link('/user_zone?param=text', 'one more time')+'</li>',
        '</ul>'
    )

    for line in get_header("Root") + body + get_footer():
        yield line.encode()+b'\n'


@app.route('/user')
@check_digest(USER, 'user')
def user_only(req):
    """Page for user only."""
    body = (
        '<h2>User test for %s algorithm.</h2>' % app.auth_algorithm,
        'User: %s' % req.user,
        '<ul>',
        '<li>'+get_link('/', 'Root')+'</li>',
        '<li>'+get_link('/admin?param=1234', 'one more time')+'</li>',
        '</ul>'
    )

    for line in get_header("Root") + body + get_footer():
        yield line.encode()+b'\n'


@app.route('/foo')
@check_digest(USER, 'foo')
def foo_only(req):
    """Page for foo user only."""
    body = (
        '<h2>Foo test for %s algorithm.</h2>' % app.auth_algorithm,
        'User: %s' % req.user,
        '<ul>',
        '<li>'+get_link('/', 'Root')+'</li>',
        '</ul>',
        '<form method="post" action="/foo/passwd">',
        '<label>Enter new password:',
        '<input type="password" name="password"/>',
        '</label>',
        '<button type="submit">Change Password</button>',
        '</form>'
    )

    for line in get_header("Root") + body + get_footer():
        yield line.encode()+b'\n'


@app.route('/foo/passwd', method=state.METHOD_POST)
@check_digest(USER, 'foo')
def foo_password(req):
    """Change foo's password."""
    digest = hexdigest(req.user, USER, req.form.get('password'),
                       app.auth_hash)
    app.auth_map.set(USER, req.user, digest)
    redirect('/foo')


@app.route('/unknown')
@check_digest(USER, 'unknown')
def unknown_endpoint(req):
    """Page for digest test."""
    return EmptyResponse()


if __name__ == '__main__':
    # pylint: disable=invalid-name
    httpd = make_server('0.0.0.0', 8080, app)
    logging.info("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
