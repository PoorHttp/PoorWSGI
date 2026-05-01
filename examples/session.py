"""Session + JWT example.

Demonstrates ``Session`` (plain cookie) combined with PyJWT for stateless
authentication.  The server issues a signed JWT on login and stores it in a
``Session`` cookie.  On every protected request the JWT is read from the
cookie and verified — no server-side state is required.

Run::

    pip install PyJWT
    python examples/session.py

Then open http://127.0.0.1:8080 in your browser.
Login with any non-empty username and password ``secret``.
"""
import logging
from functools import wraps
from os import path, urandom
from sys import path as python_path
from time import time

import jwt  # PyJWT

python_path.insert(
    0, path.abspath(path.join(path.dirname(__file__), path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.response import HTTPException, RedirectResponse, redirect  # noqa
from poorwsgi.session import Session  # noqa

# pylint: disable=unused-argument

logging.getLogger().setLevel("DEBUG")

app = application = Application(__name__)  # pylint: disable=invalid-name
app.debug = True

# Secret used both for the JWT signature and (optionally) session protection.
SECRET = urandom(32)
PASSWORD = "secret"  # nosec  # noqa: S105
JWT_EXPIRY = 3600  # seconds


# --- helpers -----------------------------------------------------------------

def get_header(title):
    """Returns HTML page header lines."""
    return (
        "<html>", "<head>",
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
        f"<title>{title}</title>", "</head>", "<body>",
        f"<h1>{title}</h1>")


def get_footer():
    """Returns HTML page footer lines."""
    return ("<hr>", "<small>Session + JWT example — PoorWSGI</small>",
            "</body>", "</html>")


def check_login(fn):
    """Decorator that reads and verifies the JWT stored in the session cookie.

    Sets ``req.login`` to the JWT payload on success, otherwise redirects to
    ``/login``.
    """
    @wraps(fn)
    def handler(req):
        session = Session()
        session.load(req.cookies)
        token = session.data
        if not token:
            redirect("/login", message=b"Login required")
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            redirect("/login", message=b"Session expired or invalid")
        req.login = payload
        return fn(req)
    return handler


# --- routes ------------------------------------------------------------------

@app.route('/')
def root(_req):
    """Index page with navigation."""
    body = ('<ul>',
            '<li><a href="/login">/login</a> — log in</li>',
            '<li><a href="/private">/private</a> — protected page</li>',
            '<li><a href="/logout">/logout</a> — log out</li>',
            '</ul>')
    for line in get_header("Session + JWT demo") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/login')
def login_form(_req):
    """GET: show login form."""
    form = ('<form method="post">',
            '<label>Username: '
            '<input type="text" name="username"/></label><br/>',
            '<label>Password: <input type="password" name="password"/>'
            '</label><br/>',
            '<button type="submit">Login</button>', '</form>',
            '<p><em>Password is: secret</em></p>')
    for line in get_header("Login") + form + get_footer():
        yield line.encode() + b'\n'


@app.route('/login', method=state.METHOD_POST)
def login_post(req):
    """POST: validate credentials and issue JWT."""
    username = req.form.getfirst('username', func=str) or ''
    password = req.form.getfirst('password', func=str) or ''

    if not username or password != PASSWORD:
        redirect('/login')

    token = jwt.encode(
        {"sub": username, "exp": int(time()) + JWT_EXPIRY},
        SECRET, algorithm="HS256")

    response = RedirectResponse("/private")
    session = Session(secure=False, same_site="Lax")
    session.data = token
    session.write()
    session.header(response)
    raise HTTPException(response)


@app.route('/private')
@check_login
def private(req):
    """A protected page — only accessible after login."""
    user = req.login.get("sub", "?")
    exp = req.login.get("exp", 0)
    body = (f'<p>Hello, <strong>{user}</strong>!</p>',
            f'<p>Your token expires at Unix time {exp}.</p>',
            '<p><a href="/logout">Log out</a></p>')
    for line in get_header("Private page") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/logout')
def logout(_req):
    """Clears the session cookie."""
    response = RedirectResponse("/login")
    session = Session()
    session.destroy()
    session.header(response)
    raise HTTPException(response)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server  # noqa: E402
    httpd = make_server(  # pylint: disable=invalid-name
        '127.0.0.1', 8080, app)
    logging.info("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
