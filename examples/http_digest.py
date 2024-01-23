"""HTTP WWW-Authenticate Digest Example."""
import logging
from hashlib import sha256
from os import path
from sys import path as python_path
from time import time
from wsgiref.simple_server import make_server

python_path.insert(
    0, path.abspath(path.join(path.dirname(__file__), path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.digest import PasswordMap, check_digest, hexdigest  # noqa
from poorwsgi.response import EmptyResponse, redirect  # noqa

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
# user/looser, foo/bar, admin/admin, Ondřej/heslíčko
app.auth_map = PasswordMap(FILE)
app.auth_map.load()

# pylint: disable=unused-argument


def get_header(title):
    """Return HTML header list of lines."""
    return (
        "<html>", "<head>",
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
        f"<title>{__file__} - {title}</title>", "</head>", "<body>",
        f"<h1>{__file__} - {title}</h1>")


def get_footer():
    """Return HTML footer list of lines."""
    return ("<hr>", "<small>Copyright (c) 2020 Ondřej Tůma. See ",
            '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>'
            '</small>.', "</body>", "</html>")


def get_link(href, text=None, title=None):
    """Return HTML anchor."""
    text = text or title or href
    title = title or text
    return f'<a href="{href}" title="{title}">{text}</a>'


@app.route('/')
def root(req):
    """Return Root (Index) page."""
    body = ('<ul>', "<li>" + get_link('/admin_zone') +
            " - admin zone (admin/admin)</li>", "<li>" +
            get_link('/user_zone') + " - user zone (user/looser;sha/sha)</li>",
            "<li>" + get_link('/user') + " - user (user/looser)</li>", "<li>" +
            get_link('/user/utf-8') + " - utf-8 (Ondřej/heslíčko)</li>",
            "<li>" + get_link('/foo') + " - foo (foo/bar)</li>",
            "<li>" + get_link('/unknown') + " - unknown</li>",
            "<li>" + get_link('/spaces in url') + " - spaces in url</li>",
            "<li>" + get_link('/čeština v url') + " - diacitics in url</li>",
            "<li>" + get_link('/crazy in url 🤪') + " - unicode in url</li>",
            '</ul>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/admin_zone')
@check_digest(ADMIN)
def admin_zone(req):
    """Page only for ADMIN realm."""
    body = (f'<h2>{ADMIN} test for {app.auth_algorithm} algorithm.</h2>',
            '<ul>', '<li>' + get_link('/', 'Root') + '</li>',
            '<li>' + get_link('/admin_zone?arg=42', 'one more time') + '</li>',
            '</ul>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/user_zone')
@check_digest(USER)
def user_zone(req):
    """Page for USER realm."""
    body = (f'<h2>{USER} test for {app.auth_algorithm} algorithm.</h2>',
            f'User: {req.user}', '<ul>',
            '<li>' + get_link('/', 'Root') + '</li>', '<li>' +
            get_link('/user_zone?param=text', 'one more time') + '</li>',
            '</ul>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/user')
@check_digest(USER, 'user')
def user_only(req):
    """Page for user only."""
    body = (f'<h2>User test for {app.auth_algorithm} algorithm.</h2>',
            f'User: {req.user}', '<ul>',
            '<li>' + get_link('/', 'Root') + '</li>', '<li>' +
            get_link('/user?param=1234', 'one more time') + '</li>', '</ul>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/foo')
@check_digest(USER, 'foo')
def foo_only(req):
    """Page for foo user only."""
    body = (f'<h2>Foo test for {app.auth_algorithm} algorithm.</h2>',
            f'User: {req.user}', '<ul>', '<li>' + get_link('/', 'Root') +
            '</li>', '</ul>', '<form method="post" action="/foo/passwd">',
            '<label>Enter new password:',
            '<input type="password" name="password"/>', '</label>',
            '<button type="submit">Change Password</button>', '</form>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/user/utf-8')
@check_digest(USER, 'Ondřej')
def utf8_chars(req):
    """Page for user only."""
    body = (f'<h2>User test for {app.auth_algorithm} algorithm.</h2>',
            f'User: {req.user}', '<ul>',
            '<li>' + get_link('/', 'Root') + '</li>', '<li>' +
            get_link('/user/utf-8?param=1234', 'one more time') + '</li>',
            '</ul>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/foo/passwd', method=state.METHOD_POST)
@check_digest(USER, 'foo')
def foo_password(req):
    """Change foo's password."""
    digest = hexdigest(req.user, USER, req.form.get('password'), app.auth_hash)
    app.auth_map.set(USER, req.user, digest)
    redirect('/foo')


@app.route('/unknown')
@check_digest(USER, 'unknown')
def unknown_endpoint(req):
    """Page for digest test."""
    return EmptyResponse()


def generic_response(url, user):
    """Return generic response"""
    body = (f'<h2>{USER} test for {app.auth_algorithm} algorithm.</h2>',
            f'User: {user}', '<ul>', '<li>' + get_link('/', 'Root') + '</li>',
            '<li>' + get_link(url + '?param=text', 'one more time') + '</li>',
            '</ul>')

    for line in get_header("Root") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/spaces in url')
@check_digest(USER)
def spaces_in_url(req):
    """URL with spaces in path."""
    return generic_response(req.path, req.user)


@app.route('/čeština v url')
@check_digest(USER)
def diacritics_in_url(req):
    """URL with diacritics in path."""
    return generic_response(req.path, req.user)


@app.route('/crazy in url 🤪')
@check_digest(USER)
def crazy_in_url(req):
    """URL with unicode in path."""
    return generic_response(req.path, req.user)


if __name__ == '__main__':
    # pylint: disable=invalid-name
    httpd = make_server('127.0.0.1', 8080, app)
    logging.info("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
