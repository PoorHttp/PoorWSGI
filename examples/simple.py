# -*- coding: utf-8 -*-
#
# This is example and test application for PoorWSGI connector.
#
# This sample testing example is free to use, modify and study under same BSD
# licence as PoorWSGI. So enjoy it ;)

from wsgiref.simple_server import make_server
from base64 import decodebytes, encodebytes
from json import dumps
from collections import OrderedDict
from io import FileIO as file
from sys import path as python_path
from tempfile import TemporaryFile
from functools import wraps

import os
import logging as log

EXAMPLES_PATH = os.path.dirname(__file__)           # noqa
python_path.insert(0, os.path.abspath(              # noqa
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

from poorwsgi import Application, state, request, redirect
from poorwsgi.session import PoorSession
from poorwsgi.response import Response, RedirectResponse, FileResponse, \
    JSONResponse, JSONGeneratorResponse, EmptyResponse, HTTPException

logger = log.getLogger()
logger.setLevel("DEBUG")
app = application = Application("simple")
app.debug = True
app.document_root = '.'
app.document_index = True
app.secret_key = os.urandom(32)     # random key each run


class Storage(file):
    def __init__(self, directory, filename):
        log.debug("directory: %s; filename: %s", directory, filename)
        self.path = directory + '/' + filename

        if os.access(self.path, os.F_OK):
            raise Exception("File %s exist yet" % filename)

        super(Storage, self).__init__(self.path, 'w+b')


class StorageFactory:
    def __init__(self, directory):
        self.directory = directory
        if not os.access(directory, os.R_OK):
            os.mkdir(directory)

    def create(self, filename):
        if filename:
            return Storage(self.directory, filename)
        return TemporaryFile("wb+")


app.auto_form = False


@app.before_request()
def log_request(req):
    log.info("Before request")
    log.info("Data: %s" % req.data)


@app.before_request()
def auto_form(req):
    """ This is own implementation of req.form paring before any POST request
        with own file_callback.
    """
    if req.method_number == state.METHOD_POST:
        factory = StorageFactory('./upload')
        try:
            req.form = request.FieldStorage(
                req, keep_blank_values=app.keep_blank_values,
                strict_parsing=app.strict_parsing,
                file_callback=factory.create)
        except Exception:
            log.exception()


def get_crumbnav(req):
    navs = [req.hostname]
    if req.uri == '/':
        navs.append('<b>/</b>')
    else:
        navs.append('<a href="/">/</a>')
        navs.append('<b>%s</b>' % req.uri)
    return " &raquo; ".join(navs)


def html(s):
    s = str(s)
    s = s.replace('&', '&amp;')
    s = s.replace('>', '&gt;')
    s = s.replace('<', '&lt;')
    return s


def get_header(title):
    return (
        "<html>",
        "<head>",
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
        "<title>Simple.py - %s</title>" % title,
        '<link rel="stylesheet" href="/style.css">',
        "</head>",
        "<body>",
        "<h1>Simple.py - %s</h1>" % title
    )


def get_footer():
    return (
        "<hr>",
        "<small>Copyright (c) 2013 Ondřej Tůma. See ",
        '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>'
        '</small>.',
        "</body>",
        "</html>"
    )


def get_variables(req):
    usable = ("REQUEST_METHOD", "QUERY_STRING", "SERVER_NAME", "SERVER_PORT",
              "REMOTE_ADDR", "REMOTE_HOST", "PATH_INFO")
    return sorted(tuple(
        (key, html(val)) for key, val in req.environ.items()
        if key.startswith("wsgi.") or key.startswith("poor_") or
        key in usable))


app.set_filter('email', r'[\w\.\-]+@[\w\.\-]+')


def check_login(fn):
    @wraps(fn)
    def handler(req):
        cookie = PoorSession(req)
        if 'login' not in cookie.data:
            log.info('Login cookie not found.')
            redirect("/", message="Login required",)
        return fn(req)
    return handler


@app.route('/')
def root(req):
    buff = get_header("Index") + (
        get_crumbnav(req),
        "<ul>",
        '<li><a href="%s">/</a> - This Page</li>' % req.construct_url('/'),
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
def favicon(req):
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
def style(req):
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
@app.route('/test/static')
def test_dynamic(req, variable=None):
    var_info = {'type': type(variable),
                'value': variable,
                'uri_rule': req.uri_rule}

    title = "Variable" if variable is not None else "Static"

    buff = get_header(title + " test") + \
        (get_crumbnav(req),
         "<h2>Variable</h2>",
         "<table>") + \
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, html(val)) for key, val in var_info.items()) + \
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


@app.route('/test/<variable:re:.*>')
@app.route('/test/<variable0>/<variable1>/<variable2>')
def test_varargs(req, *args):
    var_info = {'len': len(args),
                'uri_rule': req.uri_rule}
    var_info.update(req.groups)

    buff = get_header("Variable args test") + \
        (get_crumbnav(req),
         "<h2>Variables</h2>",
         "<table>") + \
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, html(val)) for key, val in var_info.items()) + \
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


@app.route('/login')
def login(req):
    log.debug("Input cookies: %s", repr(req.cookies))
    cookie = PoorSession(req)
    cookie.data['login'] = True
    response = RedirectResponse('/')
    cookie.header(response)
    return response


@app.route('/logout')
def logout(req):
    log.debug("Input cookies: %s", repr(req.cookies))
    cookie = PoorSession(req)
    cookie.destroy()
    response = RedirectResponse('/')
    cookie.header(response)
    return response


@app.route('/test/form', method=state.METHOD_GET_POST)
@check_login
def test_form(req):
    # get_var_info = {'len': len(args)}
    var_info = OrderedDict((
        ('form_keys', req.form.keys()),
        ('form_values', ', '.join(tuple(str(req.form.getvalue(key))
                                  for key in req.form.keys()))),
        ('form_getfirst', '%s,%s' % (req.form.getfirst('pname'),
                                     req.form.getfirst('px'))),
        ('form_getlist', '%s,%s' % (list(req.form.getlist('pname')),
                                    list(req.form.getlist('px')))),
        ('', ''),
        ('args_keys', req.args.keys()),
        ('args_values', ', '.join(tuple(str(req.args[key])
                                        for key in req.args.keys()))),
        ('args_getfirst', '%s,%s' % (req.args.getfirst('gname'),
                                     req.args.getfirst('gx'))),
        ('args_getlist', '%s,%s' % (list(req.args.getlist('gname')),
                                    list(req.args.getlist('gx')))),
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
         "<h2>Post Form</h2>",
         '<form method="post">',
         '<input type="text" name="pname" value="Ondřej"><br/>',
         '<input type="text" name="psurname" value="Tůma"><br/>',
         '<input type="text" name="px" value="8">'
         '<input type="text" name="px" value="7">'
         '<input type="text" name="px" value="6"><br/>',
         '<input type="submit" name="btn" value="Send">'
         '</form>',
         "<h2>Variables</h2>",
         "<table>") + \
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, html(val)) for key, val in var_info.items()) + \
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
    var_info = OrderedDict((
        ('form_keys', req.form.keys()),
        ('form_value_names', ', '.join(tuple(req.form[key].name
                                             for key in req.form.keys()))),
        ('form_value_types', ', '.join(tuple(req.form[key].type
                                             for key in req.form.keys()))),
        ('form_value_fnames', ', '.join(tuple(str(req.form[key].filename)
                                              for key in req.form.keys()))),
        ('form_value_lenghts', ', '.join(tuple(str(req.form[key].length)
                                               for key in req.form.keys()))),
        ('form_value_files', ', '.join(tuple(str(req.form[key].file)
                                             for key in req.form.keys()))),
        ('form_value_lists', ', '.join(tuple(
            'Yes' if req.form[key].list else 'No'
            for key in req.form.keys()))),
        ))

    files = []
    for key in req.form.keys():
        if req.form[key].filename:
            files.append("<h2>%s</h2>" % req.form[key].filename)
            files.append("<i>%s</i>" % req.form[key].type)
            if req.form[key].type.startswith('text/'):
                files.append("<pre>%s</pre>" %
                             html(req.form.getvalue(key).decode('utf-8')))
            else:
                files.append("<pre>%s</pre>" %
                             encodebytes(req.form.getvalue(key)).decode())
            os.remove("./upload/%s" % (req.form[key].filename))

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
        tuple("<tr><td>%s:</td><td>%s</td></tr>" %
              (key, html(val)) for key, val in var_info.items()) + \
        ("</table>",) + \
        tuple(files) + \
        get_footer()

    response = Response()
    for line in buff:
        response.write(line + '\n')
    return response


@app.http_state(state.HTTP_NOT_FOUND)
def not_found(req):
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
        "<p>Your reqeuest <code>%s</code> was not found.</p>" % req.uri,
    ) + get_footer()

    response = Response(status_code=state.HTTP_NOT_FOUND)
    for line in buff:
        response.write(line + '\n')
    return response


@app.route('/test/headers')
def test_headers(req):
    return dumps(
        {"Content-Type": (req.mime_type, req.charset),
         "Content-Length": req.content_length,
         "Host": req.hostname,
         "Accept": req.accept,
         "Accept-Charset": req.accept_charset,
         "Accept-Encoding": req.accept_encoding,
         "Accept-Language": req.accept_language,
         "Accept-MimeType": {
            "html": req.accept_html,
            "xhtml": req.accept_xhtml,
            "json": req.accept_json
         },
         "XMLHttpRequest": req.is_xhr}
    ), "application/json"


@app.route('/test/json', method=state.METHOD_GET_POST)
def test_json(req):
    return JSONResponse(status_code=418, message="I'm teapot :-)",
                        numbers=list(range(5)),
                        request=req.json)


@app.route('/test/json-generator', method=state.METHOD_GET)
def test_json_generator(req):
    return JSONGeneratorResponse(status_code=418, message="I'm teapot :-)",
                                 numbers=range(5),
                                 request=req.json)


@app.route('/test/empty')
def test_empty(req):
    res = EmptyResponse(state.HTTP_OK)
    res.add_header("Super-Header", "SuperValue")
    return res


@app.route('/yield')
def yielded(req):
    for i in range(10):
        yield b"line %d\n" % i


@app.route('/simple.py')
def simple_py(req):
    return FileResponse(__file__)


@app.after_request()
def log_response(req, res):
    log.info("After request")
    return res


@app.route('/timestamp')
def get_timestamp(req):
    return JSONResponse(timestamp=req.timestamp)


@app.route('/internal-server-error')
def method_raises_errror(req):
    raise RuntimeError('Test of internal server error')


@app.route('/none-error')
def none_error_handler(req):
    return None


@app.route('/bad-request')
def bad_request(req):
    raise HTTPException(state.HTTP_BAD_REQUEST)


@app.route('/forbidden')
def forbidden(req):
    raise HTTPException(state.HTTP_FORBIDDEN)


@app.route('/not-implemented')
def not_implemented(req):
    raise HTTPException(state.HTTP_NOT_IMPLEMENTED)


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
