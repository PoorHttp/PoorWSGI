"""This is example and test application for PoorWSGI connector.

This sample testing example is free to use, modify and study under same BSD
licence as PoorWSGI. So enjoy it ;)
"""

import logging as log
import os
from base64 import decodebytes, encodebytes, urlsafe_b64encode
from collections import OrderedDict
from functools import wraps
from hashlib import md5
from io import BytesIO
from io import FileIO as file
from os.path import getctime
from random import choices
from sys import path as python_path
from wsgiref.simple_server import make_server

EXAMPLES_PATH = os.path.dirname(__file__)
python_path.insert(
    0, os.path.abspath(os.path.join(EXAMPLES_PATH, os.path.pardir)))

# pylint: disable=import-error, wrong-import-position
from poorwsgi import Application, redirect, state  # noqa
from poorwsgi.fieldstorage import FieldStorageParser  # noqa
from poorwsgi.headers import http_to_time, parse_range, time_to_http  # noqa
from poorwsgi.response import FileResponse  # noqa
from poorwsgi.response import HTTPException  # noqa
from poorwsgi.response import (FileObjResponse, GeneratorResponse,  # noqa
                               NoContentResponse, NotModifiedResponse,
                               PartialResponse, RedirectResponse, Response)
from poorwsgi.results import html_escape, not_modified  # noqa
from poorwsgi.session import PoorSession, SessionError  # noqa

try:
    import uwsgi  # type: ignore

except ModuleNotFoundError:
    uwsgi = None  # pylint: disable=invalid-name

logger = log.getLogger()
logger.setLevel("DEBUG")
app = application = Application("simple")
app.debug = True
app.document_root = '.'
app.document_index = True
app.secret_key = os.urandom(32)  # random key each run


class MyValueError(ValueError):
    """My value error"""


class Storage(file):
    """File storage class created by StorageFactory."""

    def __init__(self, directory, filename):
        log.debug("directory: %s; filename: %s", directory, filename)
        self.path = directory + '/' + filename

        if os.access(self.path, os.F_OK):
            msg = f"File {filename} exist yet"
            raise OSError(msg)

        super().__init__(self.path, 'w+b')


class StorageFactory:
    """Storage Factory do some code before creating file."""

    # pylint: disable=too-few-public-methods

    def __init__(self, directory):
        self.directory = directory
        if not os.access(directory, os.R_OK):
            os.mkdir(directory)

    def create(self, filename):
        """Create file in directory."""
        if not filename:
            return BytesIO()
        return Storage(self.directory, filename)


app.auto_form = False


@app.before_response()
def log_request(req):
    """Log each request before processing."""
    log.info("Before response")
    log.info("Headers: %s", req.headers)
    log.info("Data: %s", req.data)


@app.before_response()
def auto_form(req):
    """ This is own implementation of req.form paring before any POST response
        with own file_callback.
    """
    if req.is_body_request or req.server_protocol == "HTTP/0.9":
        factory = StorageFactory('./upload')
        try:
            parser = FieldStorageParser(
                    req.input, req.headers,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing,
                    file_callback=factory.create)
            req.form = parser.parse()
        except Exception as err:  # pylint: disable=broad-except
            log.exception("Exception %s", str(err))
            raise


def get_crumbnav(req):
    """Create crumb navigation from url."""
    navs = [req.hostname]
    if req.uri == '/':
        navs.append('<b>/</b>')
    else:
        navs.append('<a href="/">/</a>')
        navs.append(f'<b>{req.uri}</b>')
    return " &raquo; ".join(navs)


def get_header(title):
    """Return HTML header."""
    return (
        "<html>", "<head>",
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
        f"<title>Simple.py - {title}</title>",
        '<link rel="stylesheet" href="/style.css">', "</head>", "<body>",
        f"<h1>Simple.py - {title}</h1>")


def get_footer():
    """Return HTML footer."""
    return ("<hr>", "<small>Copyright (c) 2013-2021 Ondřej Tůma. See ",
            '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>'
            '</small>.', "</body>", "</html>")


def get_variables(req):
    """Return some environment variables and it's values."""
    usable = ("REQUEST_METHOD", "QUERY_STRING", "SERVER_NAME", "SERVER_PORT",
              "REMOTE_ADDR", "REMOTE_HOST", "PATH_INFO")
    return sorted(
        tuple((key, html_escape(repr(val)))
              for key, val in req.environ.items() if key.startswith("wsgi.")
              or key.startswith("poor_") or key in usable))


app.set_filter('email', r'[\w\.\-]+@[\w\.\-]+')


def check_login(fun):
    """Check session cookie."""

    @wraps(fun)
    def handler(req):
        session = PoorSession(app.secret_key)
        try:
            session.load(req.cookies)
        except SessionError:
            pass
        if 'login' not in session.data:
            log.info('Login cookie not found.')
            redirect(
                "/",
                message="Login required",
            )
        return fun(req)

    return handler


@app.route('/')
def root(req):
    """Return root index."""
    buff = get_header("Index") + (
        get_crumbnav(req),
        "<ul>",
        '<li><a href="' + req.construct_url('/') + '">/</a> - This Page</li>',
        '<li><a href="/test/static">/test/static</a> - Testing Static Page'
        '</li>',
        '<li><a href="/test/42">/test/&lt;variable:int&gt;</a>'
        ' - Testing regular:int Page</li>',
        '<li><a href="/test/3.14">/test/&lt;variable:float&gt;</a>'
        ' - Testing regular:float Page</li>',
        '<li><a href="/test/word">/test/&lt;variable:word&gt;</a>'
        ' - Testing regular:word Page</li>',
        '<li><a href="/test/user@example.net">/test/&lt;variable:user&gt;</a>'
        ' - Testing regular:user Page</li>',
        '<li><a href="/test/[grr]">/test/&lt;variable:re:.*&gt;</a>'
        ' - Testing regular:re Page</li>',
        '<li><a href="/test/one/too/three">'
        '/test/&lt;variable0&gt;/&lt;variable1&gt;/&lt;variable2&gt;</a>'
        ' - Testing variable args</li>',
        '<li><a href="/test/headers">/test/headers</a> - Testing Headers'
        '</li>',
        '<li><a href="/login">/login</a> - Create login session</li>',
        '<li><a href="/logout">/logout</a> - Destroy login session</li>',
        '<li><a href="/test/form">/test/form</a>'
        ' - Testing http form (only if you have login cookie / session)</li>',
        '<li><a href="/test/upload">/test/upload</a> - '
        'Testing file upload (only if you have login cookie / session)</li>',
        '<li><a href="/debug-info">/debug-info</a>'
        ' - Debug Page (only if poor_Debug is set)</li>',
        '<li><a href="/no-page">/no-page</a> - No Exist Page</li>',
        '<li><a href="/internal-server-error">/internal-server-error</a>'
        ' - Inernal Server Error</li>',
        "</ul>",
    ) + get_footer()
    response = Response()
    for line in buff:
        response.write(line + '\n')
    return response


@app.route('/favicon.ico')
def favicon(_):
    """Return favicon."""
    icon = b"""
AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAD///8A////AP///wD///8AFRX/Bw8P/24ICP/IAgL/7wAA/+oAAP/GAAD/bQAA/wj///8A
////AP///wD///8A////AP///wD///8A////AB4e/4gYGP//ERH//wsL//8EBP//AAD/1QAA/6AA
AP+C////AP///wD///8A////AP///wD///8A////AP///wAnJ//dISH//xsb//8UFP//Dg7//wcH
/9cBAf+kAAD/1f///wD///8A////AP///wD///8A////AP///wD///8AMTH/4Coq//8kJP//HR3/
/xcX/7AQEP+wCgr/sAMD/5T///8A////AP///wD///8AAHo+BwB3O4AAczjSAHA1jTo6/+AzM///
LS3//yYm//8gIP/YGRn/2BMT/9gNDf/YBgb/2AAA/9UAAP+HAAD/BgB9QGwAej3/AHY6/wBzOKg9
Pf/fPDz//zY2//8vL///KSn//yMj//8cHP//Fhb//w8P//8JCf//AgL//wAA/2oAgELGAH1A/wB5
Pf8AdjrkPD79nz09//89Pf//OTn//zIy//8sLP//JSX//x8f//8YGP//EhL//wwM//8FBf/HAINF
6wCAQv8AfD//AHk8/wtrXYw8PvqUPT3/zz09/9A7O//QNTX/0C4u//koKP//IiL//xsb//8VFf//
Dg7/7wCHR+8Ag0T/AH9B/wB8P/8AeDz/AHU57ABxN7gAbjS4AGoxuABpMLcKYVSFLzP3nysr//8k
JP//Hh7//xcX/+sAiknKAIZH/wCDRP8Af0H/AHs+/wB4PP8AdDn/AHE2/wBtM/8AajH/AGkw/wVl
QZE0NP/xLS3//ycn//8gIP/JAI1MagCJSf8Ahkb/AIJD/wB/Qf8Aez7/AHg7/wB0Of8AcDb/AG0z
/wBpMP8AaTDVPT3/sjY2//8wMP//Kir/egCQTgIAjEuGAIlJ1QCFRugAgkPoAH5A6AB7PugAdzvo
AHQ4/wBwNf8AbDP/AGkw1z09/589Pf/lOTn/mzMz/w7///8A////AP///wD///8AAIVFhQCBQ5gA
fkCYAHo9mAB3O/8Aczj/AG81/wBsMtj///8A////AP///wD///8A////AP///wD///8A////AACI
SN8AhEW0AIFC5wB9QP8Aej3/AHY6/wBzN/8AbzXX////AP///wD///8A////AP///wD///8A////
AP///wAAi0q1AIdHhwCERc4AgEL/AH0//wB5PP8Adjr/AHI3k////wD///8A////AP///wD///8A
////AP///wD///8AAI5NJQCKSpkAh0fhAINE9wCAQvQAfD/fAHk8jwB1ORT///8A////AP///wD/
//8A/D8AAPAPAADwDwAA8A8AAIABAACAAQAAAAAAAAAAAAAAAAAAAAAAAIABAACAAQAA8A8AAPAP
AADwDwAA+B8AAA==
"""
    return decodebytes(icon), "image/vnd.microsoft.icon"


@app.route('/style.css')
def style(_):
    """Return stylesheet."""
    buff = """
        body { width: 90%; max-width: 900px; margin: auto;
        padding-top: 30px; }
        h1 { text-align: center; color: #707070; }
        p { text-indent: 30px; margin-top: 30px; margin-bottom: 30px; }
        pre { font-size: 90%; background: #ddd; overflow: auto; }
        table { width: 100%; font-family: monospace; }
        td { word-break:break-word; }
        td:first-child { white-space: nowrap; word-break:keep-all; }
        tr:hover { background: #e0e0e0; }
    """
    return buff, "text/css"


@app.route('/test/<variable:email>')
@app.route('/test/<variable:word>')
@app.route('/test/<variable:float>')
@app.route('/test/<variable:int>')
@app.route('/test/<variable:uuid>')
@app.route('/test/static')
def test_dynamic(req, variable=None):
    """Test dynamics values."""
    if not variable and req.headers.get('ETag') == 'W/"0123"':
        return not_modified(req)

    var_info = {
        'type': html_escape(repr(type(variable))),
        'value': html_escape(repr(variable)),
        'uri_rule': html_escape(req.uri_rule),
    }

    title = "Variable" if variable is not None else "Static"

    buff = get_header(title + " test") + \
        (get_crumbnav(req),
         "<h2>Variable</h2>",
         "<table>") + \
        tuple(f"<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in var_info.items()) + \
        ("</table>",
         "<h2>Browser Headers</h2>",
         "<table>") + \
        tuple(f"<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in req.headers.items()) + \
        ("</table>",
         "<h2>Request Variables </h2>",
         "<table>") + \
        tuple(f"<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in get_variables(req)) + \
        ("</table>",) + \
        get_footer()

    response = Response(headers={'ETag': 'W/"0123"'})
    for line in buff:
        response.write(line + '\n')
    return response


@app.route('/test/<variable:re:.*>')
@app.route('/test/<variable0>/<variable1>/<variable2>')
def test_varargs(req, *args):
    """Handler for variable path agrs"""
    var_info = {'len': len(args), 'uri_rule': html_escape(req.uri_rule)}
    for key, val in req.path_args.items():
        var_info[key] = html_escape(repr(val))

    buff = get_header("Variable args test") + \
        (get_crumbnav(req),
         "<h2>Variables</h2>",
         "<table>") + \
        tuple(f"<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in var_info.items()) + \
        ("</table>",
         "<h2>Browser Headers</h2>",
         "<table>") + \
        tuple(f"<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in req.headers.items()) + \
        ("</table>",
         "<h2>Request Variables </h2>",
         "<table>") + \
        tuple(f"<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in get_variables(req)) + \
        ("</table>",) + \
        get_footer()

    response = Response()
    for line in buff:
        response.write(line + '\n')
    return response


@app.route('/login')
def login(req):
    """Create login session cookie."""
    log.debug("Input cookies: %s", repr(req.cookies))
    cookie = PoorSession(app.secret_key)
    cookie.data['login'] = True
    response = RedirectResponse('/')
    cookie.header(response)
    return response


@app.route('/logout')
def logout(req):
    """Destroy login session cookie."""
    log.debug("Input cookies: %s", repr(req.cookies))
    cookie = PoorSession(app.secret_key)
    cookie.destroy()
    response = RedirectResponse('/')
    cookie.header(response)
    return response


@app.route('/test/form', method=state.METHOD_GET_POST)
@check_login
def test_form(req):
    """Form example"""
    # pylint: disable=consider-using-f-string
    # get_var_info = {'len': len(args)}
    var_info = OrderedDict((
        ('form_keys', ','.join(req.form.keys())),
        ('form_values', ', '.join(
            tuple(str(req.form.getvalue(key)) for key in req.form.keys()))),
        ('form_getfirst',
         '%s,%s' % (req.form.getfirst('pname'), req.form.getfirst('px'))),
        ('form_getlist', '%s,%s' %
         (list(req.form.getlist('pname')), list(req.form.getlist('px')))),
        ('', ''),
        ('args_keys', ','.join(req.args.keys())),
        ('args_values',
         ', '.join(tuple(str(req.args[key]) for key in req.args.keys()))),
        ('args_getfirst',
         '%s,%s' % (req.args.getfirst('gname'), req.args.getfirst('gx'))),
        ('args_getlist', '%s,%s' %
         (list(req.args.getlist('gname')), list(req.args.getlist('gx')))),
    ))

    buff = get_header("HTTP Form args test") + \
        (get_crumbnav(req),
         "<h2>Get Form</h2>",
         '<form method="get">',
         '<input type="text" name="gname" value="Ondřej"><br/>',
         '<input type="text" name="gsurname" value="Tůma"><br/>',
         '<input type="text" name="gx" value="1">'
         '<input type="text" name="gx" value="2">'
         '<input type="text" name="gx" value="3"><br/>',
         '<input type="submit" name="btn" value="Send">'
         '</form>',
         "<h2>Post Form multipart/form-data</h2>",
         '<form method="post" enctype="multipart/form-data">',
         '<input type="text" name="fname" value="Ondřej"><br/>',
         '<input type="text" name="fsurname" value="Tůma"><br/>',
         '<input type="text" name="fx" value="8">'
         '<input type="text" name="fx" value="7">'
         '<input type="text" name="fx" value="6"><br/>',
         '<textarea name="fbody">Some\ntext</textarea><br/>'
         '<input type="submit" name="btn" value="Send">'
         '</form>',
         "<h2>Post Form application/x-www-form-urlencoded</h2>",
         '<form method="post" enctype="application/x-www-form-urlencoded">',
         '<input type="text" name="pname" value="Ondřej"><br/>',
         '<input type="text" name="psurname" value="Tůma"><br/>',
         '<input type="text" name="px" value="8">'
         '<input type="text" name="px" value="7">'
         '<input type="text" name="px" value="6"><br/>',
         '<textarea name="fbody">Some\ntext</textarea><br/>'
         '<input type="submit" name="btn" value="Send">'
         '</form>',

         "<h2>Variables</h2>",
         "<table>") + \
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, html_escape(val)) for key, val in var_info.items()) + \
        ("</table>",
         "<h2>Browser Headers</h2>",
         "<table>") + \
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, val) for key, val in req.headers.items()) + \
        ("</table>",
         "<h2>Request Variables </h2>",
         "<table>") + \
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, val) for key, val in get_variables(req)) + \
        ("</table>",) + \
        get_footer()

    response = Response()
    for line in buff:
        response.write(line + '\n')
    return response


@app.route('/test/upload', method=state.METHOD_GET_POST)
@check_login
def test_upload(req):
    """Upload file example."""
    var_info = OrderedDict((
        ('form_keys', req.form.keys()),
        ('form_value_names', ', '.join(
            tuple(html_escape(req.form[key].name)
                  for key in req.form.keys()))),
        ('form_value_types', ', '.join(
            tuple(html_escape(req.form[key].type)
                  for key in req.form.keys()))),
        ('form_value_fnames', ', '.join(
            tuple(
                html_escape(str(req.form[key].filename))
                for key in req.form.keys()))),
        ('form_value_lenghts',
         ', '.join(tuple(str(req.form[key].length)
                         for key in req.form.keys()))),
        ('form_value_files', ', '.join(
            tuple(
                html_escape(str(req.form[key].file))
                for key in req.form.keys()))),
        ('form_value_lists', ', '.join(
            tuple('Yes' if req.form[key].list else 'No'
                  for key in req.form.keys()))),
    ))

    files = []
    for key in req.form.keys():
        if req.form[key].filename:
            files.append(f"<h2>{req.form[key].filename}</h2>")
            files.append(f"<i>{req.form[key].type}</i>")
            if req.form[key].type.startswith('text/'):
                files.append(
                    "<pre>" +
                    html_escape(req.form.getvalue(key).decode('utf-8')) +
                    "</pre>")
            else:
                files.append("<pre>" +
                             encodebytes(req.form.getvalue(key)).decode() +
                             "</pre>")
            os.remove("./upload/" + req.form[key].filename)

    buff = get_header('HTTP file upload test') + \
        (get_crumbnav(req),
         "<h2>Upload Form</h2>",
         '<form method="post" enctype="multipart/form-data">',
         '<input type="file" name="file_0"><br/>',
         '<input type="file" name="file_1"><br/>',
         '<input type="file" name="file_2"><br/>',
         '<input type="submit" name="btn" value="Upload">'
         '</form>',
         "<h2>Uploaded File</h2>",
         "<table>") + \
        tuple("<tr><td>{key}:</td><td>{val}</td></tr>"
              for key, val in var_info.items()) + \
        ("</table>",) + \
        tuple(files) + \
        get_footer()

    response = Response()
    for line in buff:
        response.write(line + '\n')
    return response


@app.http_state(state.HTTP_NOT_FOUND)
def not_found(req, *_):
    """Not found example response."""
    buff = (
        "<html>",
        "<head>",
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
        "<title>404 - Page Not Found</title>",
        '<link rel="stylesheet" href="/style.css">',
        "</head>",
        "<body>",
        "<h1>404 - Page Not Found</h1>",
        get_crumbnav(req),
        f"<p>Your reqeuest <code>{req.uri}</code> was not found.</p>",
    ) + get_footer()

    response = Response(status_code=state.HTTP_NOT_FOUND)
    for line in buff:
        response.write(line + '\n')
    return response


@app.error_handler(ValueError)
def value_error_handler(*_):
    """ValueError exception handler example."""
    log.exception("ValueError")
    raise HTTPException(state.HTTP_BAD_REQUEST)


@app.route('/test/empty')
def test_empty(req):
    """No content response"""
    assert req
    res = NoContentResponse()
    res.add_header("Super-Header", "SuperValue")
    return res


@app.route('/test/partial/unicodes')
def test_partial_unicodes(req):
    """Partial response test."""
    ranges = {}
    if 'Range' in req.headers:
        ranges = parse_range(req.headers['Range'])
    start, end = ranges.get("unicodes", {100, 199})[0]
    start = start or 100
    end = end or 199
    if end <= start:
        start = end + 100
    # ruff: noqa: S311
    res = PartialResponse(''.join(
        choices(  # nosec
            "ěščřžýáíé", k=end + 1 - start)))
    res.make_range({(start, end)}, "unicodes")
    return res


@app.route('/test/partial/empty')
def test_partial_empty(req):
    """Partial empty response test."""
    res = Response()
    ranges = {}
    if 'Range' in req.headers:
        ranges = parse_range(req.headers['Range'])
    res.make_partial(ranges.get("bytes", None))
    return res


@app.route('/test/partial/generator')
def test_partial_generator(req):
    """Partial response generator test."""

    def gen():
        for i in range(10):
            yield b"line %d\n" % i

    res = GeneratorResponse(gen(), content_length=70)
    ranges = {}
    if 'Range' in req.headers:
        ranges = parse_range(req.headers['Range'])
    res.make_partial(ranges.get("bytes", None))
    return res


@app.route('/yield')
def yielded(_):
    """Simple response generator by yield."""
    for i in range(10):
        yield b"line %d\n" % i


@app.route('/chunked')
def chunked(_):
    """Generator response with Response class."""

    def gen():
        for i in range(10):
            yield b"line %d\n" % i

    return GeneratorResponse(gen(), headers={'Transfer-Encoding': 'chanked'})


@app.route('/yield', state.METHOD_POST)
def input_stream(req):
    """Stream request handler"""
    i = 0

    # chunk must be read with extra method, uwsgi has own
    chunk = uwsgi.chunked_read() if uwsgi else req.read_chunk()
    while chunk:
        log.info("chunk: %s", chunk)
        if chunk != b'%d' % i:
            raise HTTPException(state.HTTP_BAD_REQUEST)

        chunk = uwsgi.chunked_read() if uwsgi else req.read_chunk()
        i += 1
    return NoContentResponse(status_code=state.HTTP_OK)


@app.route('/simple')
def simple(req):
    """Return simple.py with FileObjResponse"""
    assert req
    file_ = open(__file__, 'rb')  # pylint: disable=consider-using-with
    return FileObjResponse(file_)


@app.route('/simple.py')
def simple_py(req):
    """Return simple.py with FileResponse"""
    last_modified = int(getctime(__file__))
    weak = urlsafe_b64encode(
        md5(  # nosec
            last_modified.to_bytes(4, "big")).digest())
    etag = f'W/"{weak.decode()}"'

    if 'If-None-Match' in req.headers:
        if etag == req.headers.get('If-None-Match'):
            return NotModifiedResponse(etag=etag)

    if 'If-Modified-Since' in req.headers:
        if_modified = http_to_time(req.headers.get('If-Modified-Since'))
        if last_modified <= if_modified:
            return NotModifiedResponse(date=time_to_http())

    response = FileResponse(__file__, headers={'ETag': etag})
    ranges = {}
    if 'Range' in req.headers:
        ranges = parse_range(req.headers['Range'])
    response.make_partial(ranges.get("bytes", None))

    return response


@app.after_response()
def log_response(_, res):
    """Log after response created."""
    log.info("After response")
    return res


@app.route('/internal-server-error')
def method_raises_errror(_):
    """Own internal server error test"""
    raise RuntimeError('Test of internal server error')


@app.route('/none')
def none_no_content(_):
    """Test for None response."""


@app.route('/bad-request')
def bad_request(req):
    """Endpoint raises ValueError exception."""
    assert req
    raise MyValueError("ValueError exception test.")


@app.route('/forbidden')
def forbidden(req):
    """Test forbiden exception."""
    raise HTTPException(state.HTTP_FORBIDDEN)


@app.route('/not-modified')
def not_modified_result(_):
    """Test for raise not NotModifiedResponse"""
    raise HTTPException(NotModifiedResponse(etag="012"))


@app.route('/not-implemented')
def not_implemented(req):
    """Test not implemented exception"""
    raise HTTPException(state.HTTP_NOT_IMPLEMENTED)


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on http://127.0.0.1:8080")

    httpd.serve_forever()
