"""Default Poor WSGI handlers.

:Functions: not_modified, internal_server_error, bad_request, forbidden,
            not_found, method_not_allowed, not_implemented, directory_index,
            debug_info
"""

from traceback import format_exception
from time import strftime, gmtime
from os import access, listdir, R_OK, getegid, geteuid, getuid, getgid
from os.path import isfile, isdir, getsize, getctime
from operator import itemgetter
from sys import version, exc_info
from inspect import cleandoc
from logging import getLogger
from hashlib import sha256
from typing import Dict

import mimetypes

from poorwsgi.response import Response, EmptyResponse, HTTPException
from poorwsgi.state import METHOD_ALL, methods, sorted_methods, \
    HTTP_NOT_MODIFIED, HTTP_BAD_REQUEST, HTTP_UNAUTHORIZED, HTTP_FORBIDDEN, \
    HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED, HTTP_INTERNAL_SERVER_ERROR, \
    HTTP_NOT_IMPLEMENTED, \
    __version__, __date__
from poorwsgi.session import get_token

HTML_ESCAPE_TABLE = {'&': "&amp;",
                     '"': "&quot;",
                     "'": "&apos;",
                     '>': "&gt;",
                     '<': "&lt;"}

log = getLogger("poorwsgi")

# http state handlers, which is called if programmer don't defined his own
default_states: Dict[str, Dict] = {}

# pylint: disable=invalid-name


def html_escape(s):
    """Escape to html entities."""
    return ''.join(HTML_ESCAPE_TABLE.get(c, c) for c in s)


def hbytes(val):
    """Return pair value and unit."""
    unit = ('', 'k', 'M', 'G', 'T', 'P')
    u = 0
    while val > 1000 and u < len(unit):
        u += 1
        val = val / 1024.0
    return (val, unit[u])


def human_methods_(m):
    """Return methods in text."""
    if m == METHOD_ALL:
        return 'ALL'
    return ' | '.join(key for key, val in sorted_methods if val & m)


def handlers_view(handlers, sort=True):
    """Returns sorted handlers list."""
    rv = []
    for u, d in sorted(handlers.items()) if sort else handlers.items():
        vt = {}
        for m, h in d.items():
            if h not in vt:
                vt[h] = 0
            vt[h] ^= m

        for h, m in sorted(vt.items(), key=itemgetter(1)):
            rv.append((u, m, h))
    return rv


def not_modified(req):
    """Return EmptyResponse with Not Modified status."""
    # pylint: disable=unused-argument
    return EmptyResponse(HTTP_NOT_MODIFIED)


def internal_server_error(req):
    """ More debug 500 Internal Server Error server handler.

    It was be called automatically when no handlers are not defined
    in dispatch_table.errors. If poor_Debug variable is to On, Tracaback
    will be generated.
    """
    exc_type, exc_value, exc_traceback = exc_info()
    traceback = format_exception(exc_type,
                                 exc_value,
                                 exc_traceback)
    traceback = ''.join(traceback)
    log.error(traceback)
    traceback = traceback.split('\n')

    res = Response(status_code=HTTP_INTERNAL_SERVER_ERROR)

    res.write(
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>500 - Internal Server Error</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%; margin: auto; padding-top: 30px;}\n"
        "    h1 {text-align: center; color: #707070;}\n"
        "    pre .line1 {background: #e0e0e0}\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>500 - Internal Server Error</h1>\n")

    if req.debug:
        res.write(
            "  <h2>Response detail</h2>\n"
            "  remote host: <b><code>{req.remote_host}</code></b><br/>\n"
            "  remote addr: <b><code>{req.remote_addr}</code></b><br/>\n"
            "  method: <b><code>{req.method}</code></b><br/>\n"
            "  uri: <b><code>{req.uri}</code></b><br/>\n"
            "  uri_rule: <b><code>{req.uri_rule}</code></b><br/>\n"
            "  uri_handler: <b><code>{uri_handler}</code></b><br/>\n"
            "".format(req=req, uri_handler=html_escape(str(req.uri_handler))))

        res.write(
            "  <h2>Exception Traceback</h2>\n"
            "  <pre>\n")

        # Traceback
        for i, line in enumerate(traceback):
            traceback_line = html_escape(line)
            res.write('<span class="line%s">%s</span>\n' %
                      (i % 2, traceback_line))

        res.write(
            "  </pre>\n"
            "  <hr>\n"
            "  <small><i>%s / Poor WSGI for Python ,webmaster: %s</i></small>"
            "\n" % (req.server_software, req.server_admin))
    else:
        res.write(
            "  <hr>\n"
            "  <small><i>webmaster: %s </i></small>\n" % req.server_admin)
    # endif

    res.write(
        " </body>\n"
        "</html>")

    return res
# enddef


def bad_request(req):
    """ 400 Bad Request server error handler. """
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>400 - Bad Request</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%%; margin: auto; padding-top: 30px;}\n"
        "   h1 {text-align: center; color: #707070;}\n"
        "   p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>400 - Bad Request</h1>\n"
        "  <p>Method %s for %s uri.</p>\n"
        "  <hr>\n"
        "  <small><i>webmaster: %s </i></small>\n"
        " </body>\n"
        "</html>" % (req.method, req.uri, req.server_admin))
    return Response(content, status_code=HTTP_BAD_REQUEST)


def unauthorized(req, realm=None, stale=''):
    """Return 401 Unauthorized response."""
    headers = None
    if req.app.auth_type == 'Digest':
        if not realm:
            raise RuntimeError("Digest: realm value must be set")

        nonce = get_token(req.secret_key, req.user_agent,
                          timeout=req.app.auth_timeout)
        opaque = sha256(req.server_hostname.encode()).hexdigest()

        qop = req.app.auth_qop or ''
        if qop:
            qop = 'qop="%s",' % req.app.auth_qop

        header = (
            'Digest realm="{realm}",{qop}algorithm="{algorithm}",'
            'nonce="{nonce}",opaque="{opaque}"'
            ''.format(realm=realm, qop=qop, algorithm=req.app.auth_algorithm,
                      nonce=nonce, opaque=opaque))
        if stale:
            header += ',stale=true'

        # Headers could be tuple, than each header value must be another
        # available authenticate method, for example SHA-256 algorithm.
        headers = {'WWW-Authenticate': header}

    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>401 - Unauthorized</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%%; margin: auto; padding-top: 30px;}\n"
        "   h1 {text-align: center; color: #707070;}\n"
        "   p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>401 - Unauthorized</h1>\n"
        "  <p>Method %s for %s uri.</p>\n"
        "  <hr>\n"
        "  <small><i>webmaster: %s </i></small>\n"
        " </body>\n"
        "</html>" % (req.method, req.uri, req.server_admin))

    return Response(content, headers=headers, status_code=HTTP_UNAUTHORIZED)


def forbidden(req):
    """ 403 - Forbidden Access server error handler. """
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>403 - Forbidden Acces</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%%; margin: auto; padding-top: 30px;}\n"
        "   h1 {text-align: center; color: #ff0000;}\n"
        "   p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>403 - Forbidden Access</h1>\n"
        "  <p>You don't have permission to access <code>%s</code>\n"
        "   on this server.</p>\n"
        "  <hr>\n"
        "  <small><i>webmaster: %s </i></small>\n"
        " </body>\n"
        "</html>" % (req.uri, req.server_admin))
    return Response(content, status_code=HTTP_FORBIDDEN)
# enddef


def not_found(req):
    """ 404 - Page Not Found server error handler. """
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>404 - Page Not Found</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%%; margin: auto; padding-top: 30px;}\n"
        "   h1 {text-align: center; color: #707070;}\n"
        "   p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>404 - Page Not Found</h1>\n"
        "  <p>Your reqeuest <code>%s</code> was not found.</p>\n"
        "  <hr>\n"
        "  <small><i>webmaster: %s </i></small>\n"
        " </body>\n"
        "</html>" % (req.uri, req.server_admin))
    return Response(content, status_code=HTTP_NOT_FOUND)
# enddef


def method_not_allowed(req):
    """ 405 Method Not Allowed server error handler. """
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>405 - Method Not Allowed</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%%; margin: auto; padding-top: 30px;}\n"
        "   h1 {text-align: center; color: #707070;}\n"
        "   p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>405 - Method Not Allowed</h1>\n"
        "  <p>This method %s is not allowed to access <code>%s</code>\n"
        "   on this server.</p>\n"
        "  <hr>\n"
        "  <small><i>webmaster: %s </i></small>\n"
        " </body>\n"
        "</html>" % (req.method, req.uri, req.server_admin))
    return Response(content, status_code=HTTP_METHOD_NOT_ALLOWED)
# enddef


def not_implemented(req, code=None):
    """ 501 Not Implemented server error handler. """
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>501 - Not Implemented</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body {width: 80%; margin: auto; padding-top: 30px;}\n"
        "   h1 {text-align: center; color: #707070;}\n"
        "   p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"
        " </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>501 - Not Implemented</h1>\n")

    if code:
        content += (
            "  <p>Your reqeuest <code>%s</code> returned not implemented\n"
            "   status code <code>%s</code>.</p>\n" % (req.uri, code))
        log.error('Your reqeuest %s returned not implemented status code %d',
                  req.uri, code)
    else:
        content += (
            " <p>Response for Your reqeuest <code>%s</code>\n"
            "  is not implemented</p>" % req.uri)
    # endif

    content += (
        "  <hr>\n"
        "  <small><i>webmaster: %s </i></small>\n"
        " </body>\n"
        "</html>" % req.server_admin)

    return Response(content, status_code=HTTP_NOT_IMPLEMENTED)
# enddef


def directory_index(req, path):
    """Returns directory index as html page."""
    if not isdir(path):
        log.error(
            "Only directory_index can be send with directory_index handler. "
            "`%s' is not directory.",
            path)
        raise HTTPException(HTTP_INTERNAL_SERVER_ERROR)

    index = listdir(path)
    if req.document_root != path[:-1]:
        index.append("..")  # parent directory

    index.sort()

    diruri = req.uri.rstrip('/')
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        " <head>\n"
        "  <title>Index of %s</title>\n"
        '  <meta http-equiv="content-type" '
        'content="text/html; charset=utf-8"/>\n'
        "  <style>\n"
        "   body { width: 98%%; margin: auto; }\n"
        "   table { font: 90%% monospace; text-align: left; }\n"
        "   td, th { padding: 0 1em 0 1em; }\n"
        "   .size { text-align:right; white-space:pre; }\n"
        "  </style>\n"
        " </head>\n"
        " <body>\n"
        "  <h1>Index of %s</h1>\n"
        "  <hr>\n"
        "  <table>\n"
        "   <tr><th>Name</th><th>Last Modified</th>"
        "<th class=\"size\">Size</th><th>Type</th></tr>\n" % (diruri, diruri))

    for item in index:
        # dot files
        if item[0] == "." and item[1] != ".":
            continue
        # bakup files (~)
        if item[-1] == "~":
            continue

        fpath = "%s/%s" % (path, item)
        if not access(fpath, R_OK):
            continue

        fname = item + ('/' if isdir(fpath) else '')
        ftype = ""

        if isfile(fpath):
            # pylint: disable=unused-variable
            (ftype, encoding) = mimetypes.guess_type(fpath)
            if not ftype:
                ftype = 'application/octet-stream'
            size = "%.1f%s" % hbytes(getsize(fpath))
        elif isdir(fpath):
            ftype = "Directory"
            size = "-"
        else:
            size = ftype = '-'

        content += (
            "   <tr><td><a href=\"%s\">%s</a></td><td>%s</td>"
            "<td class=\"size\">%s</td><td>%s</td></tr>\n" %
            (diruri + '/' + fname,
             fname,
             strftime("%d-%b-%Y %H:%M", gmtime(getctime(fpath))),
             size,
             ftype))

    content += (
        "  </table>\n"
        "  <hr>\n")

    if req.debug:
        content += (
            "  <small><i>%s / Poor WSGI for Python, "
            "webmaster: %s </i></small>\n" %
            (req.server_software, req.server_admin)
        )
    else:
        content += ("  <small><i>webmaster: %s </i></small>\n" %
                    req.server_admin)

    content += (
        "  </body>\n"
        "</html>")

    return content
# enddef


def debug_info(req, app):
    """Return debug page.

    When Application.debug is enable, this handler is used for /debug-info.
    """
    # pylint: disable=too-many-locals
    # transform static handlers table to html
    shandlers_html = "<tr><th>Static:</th></tr>\n"
    shandlers_html += "\n".join(
        ('   <tr><td colspan="2"><a href="%s">%s</a></td>'
         '<td>%s</td><td>%s</td></tr>' %
         (u, u, human_methods_(m), f.__module__+'.'+f.__name__)
         for u, m, f in handlers_view(app.routes)))

    # regular expression handlers
    rhandlers_html = "<tr><th>Regular expression:</th></tr>\n"
    rhandlers_html += "\n".join(
        ('   <tr><td><div class="path">%s</div></td>'
         '<td>%s</td><td>%s</td><td>%s</td></tr>' %
         (html_escape(r or u.pattern),
          ', '.join(tuple("%s:<b>%s</b>" % (G, C.__name__) for G, C in c)),
          human_methods_(m),
          f.__module__+'.'+f.__name__)
         for u, m, (f, c, r) in handlers_view(app.regular_routes, False)))

    dhandlers_html = "<tr><th>Default:</th></tr>\n"
    # this function could be called by user, so we need to test req.debug
    if req.debug and 'debug-info' not in app.routes:
        dhandlers_html += ('   <tr><td colspan="2"><a href="%s">%s</a></td>'
                           '<td>%s</td><td>%s</td></tr>\n' %
                           ('/debug-info',
                            '/debug-info',
                            'ALL',
                            debug_info.__module__+'.'+debug_info.__name__))

    dhandlers_html += "\n".join(
        ('   <tr><td colspan="2">_default_handler_</td>'
         '<td>%s</td><td>%s</td></tr>' %
         (human_methods_(m),
          f.__module__+'.'+f.__name__)
         for x, m, f in handlers_view({'x': app.defaults})))

    # transform state handlers and default state table to html, users handler
    # from shandlers are preferer
    _tmp_shandlers = {}
    _tmp_shandlers.update(default_states)
    for key, val in app.states.items():
        if key in _tmp_shandlers:
            _tmp_shandlers[key].update(val)
        else:
            _tmp_shandlers[key] = val

    ehandlers_html = "\n".join(
        "   <tr><td>%s</td><td>%s</td><td>%s</td></tr>" %
        (c, human_methods_(m), f.__module__+'.'+f.__name__)
        for c, m, f in handlers_view(_tmp_shandlers))

    # pre and post table
    pre, post = app.before, app.after
    if len(pre) >= len(post):
        post += (len(pre)-len(post)) * (None, )
    else:
        pre += (len(post)-len(pre)) * (None, )

    pre_post_html = "\n".join(
        "   <tr><td>%s</td><td>%s</td></tr>" %
        (f0.__module__+'.'+f0.__name__ if f0 is not None else '',
         f1.__module__+'.'+f1.__name__ if f1 is not None else '',)
        for f0, f1 in zip(pre, post))

    # filters
    filters_html = "\n".join(
        "   <tr><td>%s</td><td>%s</td><td>%s</td></tr>" %
        (f, r, c.__name__) for f, (r, c) in app.filters.items())

    # transform actual request headers to hml
    headers_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, val) for key, val in req.headers.items()))

    # transform some poor wsgi variables to html
    poor_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, val) for key, val in (
            ('Debug', req.debug),
            ('Version', "%s (%s)" % (__version__, __date__)),
            ('Python Version', version),
            ('Server Software', req.server_software),
            ('Server Hostname', req.server_hostname),
            ('Server Port', req.server_port),
            ('Server Scheme', req.server_scheme),
            ('HTTP Hostname', req.hostname),
            ('Server Admin', req.server_admin),
            ('Forward For', req.forwarded_for),
            ('Forward Host', req.forwarded_host),
            ('Forward Proto', req.forwarded_proto),
            ('Document Root', req.document_root),
            ('Document Index', req.document_index),
            ('Secret Key', '*'*5 + ' see in error output (wsgi log)'
             ' when Log Level is <b>debug</b> ' + '*'*5)
        )))
    log.debug('SecretKey: %s', repr(req.secret_key))

    # tranform application variables to html
    app_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, val) for key, val in req.get_options().items()))

    environ = req.environ.copy()
    environ['os.pgid'] = getgid()
    environ['os.puid'] = getuid()
    environ['os.egid'] = getegid()
    environ['os.euid'] = geteuid()

    # transfotm enviroment variables to html
    environ_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, html_escape(str(val))) for key, val in sorted(environ.items())))

    content_html = cleandoc(
        """
        <!DOCTYPE html>
        <html>
         <head>
          <title>Poor Wsgi Debug info</title>
          <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
          <style>
           body { width: 80%%; margin: auto; padding-top: 30px; }
           nav { font-family: monospace; text-align: center; }
           h1 { text-align: center; color: #707070; }
           h2 { font-family: monospace; }
           table { width: 100%%; font-family: monospace; }
           table tr:nth-child(odd) { background: #e0e0e0; }
           th { padding: 10px 4px 0; text-align: left; background: #fff; }
           td { word-break:break-word; }
           td:first-child { white-space: nowrap; word-break:keep-all; }
           .path {max-width: 400px; overflow-x: auto;}
          </style>
         </head>
         <body>
          <h1>Poor Wsgi Debug Info</h1>
          <nav>
            <a href="#uri_routes">Uri routes</a>
            <a href="#state_handlers">State handlers</a>
            <a href="#before_after_handlers">Before &amp; After handlers</a>
            <a href="#filters">Filters</a>
            <a href="#headers">Headers</a>
            <a href="#poor_variables">Poor Variables</a>
            <a href="#app_variables">Aplication Variables</a>
            <a href="#environ">Environ</a>
          </nav>
          <h2 id="uri_routes">Route Table</h2>
          <table>
           %s
          </table>
          <table>
           %s
          </table>
          <table>
           %s
          </table>

          <h2 id="state_handlers">Http State Handlers Tanble</h2>
          <table>
        %s
          </table>

          <h2 id="before_after_handlers">
            Before request and After request Handlers Tanble</h2>
          <table>
           <tr><th>Before</th><th>After</th></tr>
        %s
          </table>

          <h2 id="filters">Routing regular expression filters</h2>
          <table>
        %s
          </table>

          <h2 id="headers">Request Headers</h2>
          <table>
        %s
          </table>

          <h2 id="poor_variables">Poor Request variables
           <small>(with <code>poor_</code> prefix) and Request properties
             </small></h2>
          <table>
        %s
          </table>

          <h2 id="app_variables">Application variables
           <small>(with <code>app_</code> prefix)</small></h2>
          <table>
        %s
          </table>

          <h2 id="environ">Request Environ</h2>
          <table style="font-size: 90%%;">
        %s
          </table>
          <hr>
          <small><i>%s / Poor WSGI for Python , webmaster: %s </i></small>
         </body>
        </html>""") % (shandlers_html,
                       rhandlers_html,
                       dhandlers_html,
                       ehandlers_html,
                       pre_post_html,
                       filters_html,
                       headers_html,
                       poor_html,
                       app_html,
                       environ_html,
                       req.server_software,
                       req.server_admin)

    return content_html
# enddef


def __fill_default_shandlers(code, handler):
    default_states[code] = {}
    for val in methods.values():
        default_states[code][val] = handler


__fill_default_shandlers(HTTP_NOT_MODIFIED, not_modified)
__fill_default_shandlers(HTTP_BAD_REQUEST, bad_request)
__fill_default_shandlers(HTTP_UNAUTHORIZED, unauthorized)
__fill_default_shandlers(HTTP_FORBIDDEN, forbidden)
__fill_default_shandlers(HTTP_NOT_FOUND, not_found)
__fill_default_shandlers(HTTP_METHOD_NOT_ALLOWED, method_not_allowed)
__fill_default_shandlers(HTTP_INTERNAL_SERVER_ERROR, internal_server_error)
__fill_default_shandlers(HTTP_NOT_IMPLEMENTED, not_implemented)

__all__ = ['not_modified', 'internal_server_error', 'bad_request', 'forbidden',
           'not_found', 'method_not_allowed', 'not_implemented',
           'directory_index', 'debug_info']
