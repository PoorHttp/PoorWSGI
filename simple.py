# -*- coding: utf-8 -*-

from wsgiref.simple_server import make_server
from base64 import decodestring
from poorwsgi import *
from poorwsgi.request import uni
from inspect import stack
from collections import OrderedDict

import os

def get_crumbnav(req):
    navs = [req.hostname]
    if req.uri == '/':
        navs.append('<b>/</b>')
    else:
        navs.append('<a href="/">/</a>')
        navs.append('<b>%s</b>' % req.uri)
    return " &raquo; ".join(navs)


def html(s):
    s = uni(s)
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
        '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a></small>.',
        "</body>",
        "</html>"
    )


def get_variables(req):
    usable = ("REQUEST_METHOD", "QUERY_STRING", "SERVER_NAME", "SERVER_PORT",
              "REMOTE_ADDR", "REMOTE_HOST", "PATH_INFO")
    return sorted(tuple(
        (key, html(val)) for key, val in req.environ.items() \
            if key.startswith("wsgi.") or key.startswith("poor_") or key in usable ))


app.set_filter('email', r'[\w\.\-]+@[\w\.\-]+', request.uni)

@app.route('/')
def root(req):
    buff = get_header("Index") + (
            get_crumbnav(req),
            "<ul>",
            '<li><a href="/">/</a> - This Page</li>',
            '<li><a href="/test/static">/test/static</a> - Testing Static Page</li>',
            '<li><a href="/test/42">/test/&lt;variable:int&gt;</a> - Testing regular:int Page</li>',
            '<li><a href="/test/3.14">/test/&lt;variable:float&gt;</a> - Testing regular:float Page</li>',
            '<li><a href="/test/word">/test/&lt;variable:word&gt;</a> - Testing regular:word Page</li>',
            '<li><a href="/test/user@example.net">/test/&lt;variable:user&gt;</a> - Testing regular:user Page</li>',
            '<li><a href="/test/[grr]">/test/&lt;variable:re:.*&gt;</a> - Testing regular:re Page</li>',
            '<li><a href="/test/one/too/three">/test/&lt;variable0&gt;&lt;variable1&gt;&lt;variable2&gt;</a> - Testing variable args</li>',
            '<li><a href="/test/form">/test/form</a> - Testing http form</li>',
            '<li><a href="/debug-info">/debug-info</a> - Debug Page (only if poor_Debug is set)</li>',
            '<li><a href="/no-page">/no-page</a> - No Exist Page</li>',
            "</ul>",
        ) + get_footer()
    for line in buff:
        req.write(line + '\n')
    return state.OK

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
    req.content_type = "image/vnd.microsoft.icon"
    req.write(decodestring(icon))
    return state.DONE

@app.route('/style.css')
def style(req):
    buff = (
        "body { width: 90%; max-width: 900px; margin: auto; padding-top: 30px; }",
        "h1 { text-align: center; color: #707070; }",
        "p { text-indent: 30px; margin-top: 30px; margin-bottom: 30px; }",
        "table { width: 100%; font-family: monospace; }",
        "td { word-break:break-word; }",
        "td:first-child { white-space: nowrap; word-break:keep-all; }",
        "tr:hover { background: #e0e0e0; }"
    )
    req.content_type = "text/css"
    for line in buff:
        req.write(line + '\n')
    return state.OK


@app.route('/test/<variable:email>')
@app.route('/test/<variable:word>')
@app.route('/test/<variable:float>')
@app.route('/test/<variable:int>')
@app.route('/test/static')
def test_dynamic(req, variable = None):
    var_info = {'type': type(variable),
                'value': variable,
                'uri_rule': req.uri_rule
               }

    title = "Variable" if variable is not None else "Static"

    buff = get_header(title + " test") + (
        get_crumbnav(req),
        "<h2>Variable</h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, html(val)) for key, val in var_info.items()
    ) + ("</table>",
        "<h2>Browser Headers</h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, val) for key, val in req.headers_in.items()
    ) + ("</table>",
        "<h2>Request Variables </h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, val) for key, val in get_variables(req)
    ) + ("</table>",
    ) + get_footer()

    for line in buff:
        req.write(line + '\n')
    return state.OK

@app.route('/test/<variable:re:.*>')
@app.route('/test/<variable0>/<variable1>/<variable2>')
def test_varargs(req, *args):
    var_info = {'len': len(args),
               }
    var_info.update(req.groups)

    buff = get_header("Variable args test") + (
        get_crumbnav(req),
        "<h2>Variables</h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, html(val)) for key, val in var_info.items()
    ) + ("</table>",
        "<h2>Browser Headers</h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, val) for key, val in req.headers_in.items()
    ) + ("</table>",
        "<h2>Request Variables </h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, val) for key, val in get_variables(req)
    ) + ("</table>",
    ) + get_footer()

    for line in buff:
        req.write(line + '\n')
    return state.OK

@app.route('/test/form', method = state.METHOD_GET_POST)
def test_form(req):

    #get_var_info = {'len': len(args)}
    var_info = OrderedDict((
                ('form_keys', req.form.keys()),
                ('form_values', ', '.join(tuple(uni(req.form.getvalue(key)) for key in req.form.keys()))),
                ('form_getfirst', '%s,%s' % (req.form.getfirst('pname'), req.form.getfirst('px')) ),
                ('form_getlist', '%s,%s' % ( req.form.getlist('pname'), req.form.getlist('px') )),
                ('',''),
                ('args_keys', req.args.keys()),
                ('args_values', ', '.join(tuple(uni(req.args[key]) for key in req.args.keys())) ),
                ('args_getfirst', '%s,%s' % (req.args.getfirst('gname'), req.args.getfirst('gx')) ),
                ('args_getlist', '%s,%s' % ( req.args.getlist('gname'), req.args.getlist('gx') )),
                ))
    

    buff = get_header("HTTP Form args test") + (
        get_crumbnav(req),
        "<h2>Get Form</hs>",
        '<form method="get">',
        '<input type="text" name="gname" value="Ondřej"><br/>',
        '<input type="text" name="gsurname" value="Tůma"><br/>',
        '<input type="text" name="gx" value="1">'
        '<input type="text" name="gx" value="2">'
        '<input type="text" name="gx" value="3"><br/>',
        '<input type="submit" name="btn" value="Send">'
        '</form>',
        "<h2>Post Form</hs>",
        '<form method="post">',
        '<input type="text" name="pname" value="Ondřej"><br/>',
        '<input type="text" name="psurname" value="Tůma"><br/>',
        '<input type="text" name="px" value="8">'
        '<input type="text" name="px" value="7">'
        '<input type="text" name="px" value="6"><br/>',
        '<input type="submit" name="btn" value="Send">'
        '</form>',
        "<h2>Variables</h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, html(val)) for key, val in var_info.items()
    ) + ("</table>",
        "<h2>Browser Headers</h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, val) for key, val in req.headers_in.items()
    ) + ("</table>",
        "<h2>Request Variables </h2>",
        "<table>"
    ) + tuple( "<tr><td>%s:</td><td>%s</td></tr>" % \
                            (key, val) for key, val in get_variables(req)
    ) + ("</table>",
    ) + get_footer()

    for line in buff:
        req.write(line + '\n')
    return state.OK

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

    req.status = state.HTTP_NOT_FOUND
    req.headers_out = req.err_headers_out
    for line in buff:
        req.write(line + '\n')
    return state.DONE

@app.pre_process()
@app.post_process()
def log(req):
    print "Log this point"

@app.post_process()
def post(req):
    pass

if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    httpd.serve_forever()
