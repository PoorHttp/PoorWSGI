import http

from mysession import doLogin, doLogout, checkLogin

def index(req):
    session = checkLogin(req, "/login")
    session.data['count'] = session.data.get('count', 0) + 1
    session.header(req, req.headers_out)

    req.content_type = "text/html"
    html = [
        "<html>",
        "  <head>",
        "    <title>Poor Session Example</title>",
        "  </head>",
        "  <body>",
        "     <h1>Poor Session Example</h1>",
        '     <a href="/">Refresh</a> | <a href="/dologout">Logout</a>'
        "     <p>Tuto stranku muzes videt, jen pokud jssi prihlasen.</p>",
        "     <p>You can see this page, only when you are login.</p>",
        "     <pre>%s</pre>" % str(session.data),
        "   </body>",
        "</html>",
    ]
    for line in html:
        req.write(line + '\n')
    return http.DONE
#enddef

def login(req):
    req.content_type = "text/html"
    html = [
        "<html>",
        "  <head>",
        "    <title>Poor Session Example - Login</title>",
        "  </head>",
        "  <body>",
        "     <h1>Poor Session Example - Login</h1>",
        '     <a href="/dologin">Login</a>'
        "   </body>",
        "</html>",
    ]
    for line in html:
        req.write(line + '\n')
    return http.DONE
#enddef

def dologin(req):
    doLogin(req, 'x', True)
    http.redirect(req, "/")
#enddef

def dologout(req):
    doLogout(req)
    http.redirect(req, "/login")
#enddef
