"""PoorSession example.

Demonstrates ``PoorSession`` — a self-contained encrypted and authenticated
session cookie.  User data is stored as a dictionary directly in the cookie;
no server-side session store is needed.  No external dependencies are
required.

Run::

    python examples/poor_session.py

Then open http://127.0.0.1:8080 in your browser.
Login with any non-empty username and password ``secret``.
"""
import logging
from functools import wraps
from os import path, urandom
from sys import path as python_path

python_path.insert(
    0, path.abspath(path.join(path.dirname(__file__), path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.response import HTTPException, RedirectResponse, redirect  # noqa
from poorwsgi.session import PoorSession, SessionError  # noqa

# pylint: disable=unused-argument

logging.getLogger().setLevel("DEBUG")

app = application = Application(__name__)  # pylint: disable=invalid-name
app.debug = True
app.secret_key = urandom(32)

PASSWORD = "secret"  # nosec  # noqa: S105


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
    return ("<hr>",
            "<small>PoorSession example — PoorWSGI</small>",
            "</body>", "</html>")


def check_login(fn):
    """Decorator that reads and verifies the PoorSession cookie.

    Sets ``req.login`` to the stored username on success, otherwise
    redirects to ``/login``.
    """
    @wraps(fn)
    def handler(req):
        session = PoorSession(app.secret_key)
        try:
            session.load(req.cookies)
        except SessionError:
            redirect("/login", message=b"Invalid session")
        username = session.data.get("user")
        if not username:
            redirect("/login", message=b"Login required")
        req.login = username
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
    for line in get_header("PoorSession demo") + body + get_footer():
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
    """POST: validate credentials and store username in encrypted cookie."""
    username = req.form.getfirst('username', func=str) or ''
    password = req.form.getfirst('password', func=str) or ''

    if not username or password != PASSWORD:
        redirect('/login')

    response = RedirectResponse("/private")
    session = PoorSession(app.secret_key, secure=False, same_site="Lax")
    session.data["user"] = username
    session.write()
    session.header(response)
    raise HTTPException(response)


@app.route('/private')
@check_login
def private(req):
    """A protected page — only accessible after login."""
    body = (f'<p>Hello, <strong>{req.login}</strong>!</p>',
            '<p>Your session is stored in an encrypted cookie '
            '(no external dependencies).</p>',
            '<p><a href="/logout">Log out</a></p>')
    for line in get_header("Private page") + body + get_footer():
        yield line.encode() + b'\n'


@app.route('/logout')
def logout(_req):
    """Clears the session cookie."""
    response = RedirectResponse("/login")
    session = PoorSession(app.secret_key)
    session.destroy()
    session.header(response)
    raise HTTPException(response)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server  # noqa: E402
    httpd = make_server(  # pylint: disable=invalid-name
        '127.0.0.1', 8080, app)
    logging.info("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
