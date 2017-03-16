"""Default Poor WSGI handlers."""

from traceback import format_exception
from time import strftime, gmtime
from os import path, access, listdir, R_OK, getegid, geteuid, getuid, getgid
from operator import itemgetter
from sys import version_info, version, exc_info
from inspect import cleandoc
from io import BytesIO
from json import dumps as json_dumps

import mimetypes

if version_info[0] < 3:      # python 2.x
    _unicode_exist = True

else:                           # python 3.x
    xrange = range
    _unicode_exist = False

    def cmp(a, b):
        return (a > b) - (a < b)

from poorwsgi.state import DONE, METHOD_ALL, methods, sorted_methods, levels, \
    LOG_ERR, LOG_DEBUG, HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY, \
    HTTP_NOT_MODIFIED, HTTP_BAD_REQUEST, HTTP_FORBIDDEN, HTTP_NOT_FOUND, \
    HTTP_METHOD_NOT_ALLOWED, HTTP_INTERNAL_SERVER_ERROR, \
    HTTP_NOT_IMPLEMENTED, \
    __version__, __date__

html_escape_table = {'&': "&amp;",
                     '"': "&quot;",
                     "'": "&apos;",
                     '>': "&gt;",
                     '<': "&lt;"}

# http state handlers, which is called if programmer don't defined his own
default_shandlers = {}

if _unicode_exist:
    def uni(text):
        """Automatic conversion from str to unicode with utf-8 encoding."""
        if isinstance(text, str):
            return unicode(text, encoding='utf-8')
        return unicode(text)
else:
    def uni(text):
        """Automatic conversion from str to unicode with utf-8 encoding."""
        return str(text)


def html_escape(s):
    """Escape to html entities."""
    return ''.join(html_escape_table.get(c, c) for c in s)


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


class SERVER_RETURN(Exception):
    """Compatible with mod_python.apache exception."""
    def __init__(self, code=HTTP_INTERNAL_SERVER_ERROR):
        """code is one of HTTP_* status from state module"""
        Exception.__init__(self, code)


def redirect(req, uri, permanent=0, text=None):
    """Redirect the browser to another location.

    When permanent is true, MOVED_PERMANENTLY status is sent to the client,
    otherwise it is MOVED_TEMPORARILY. A short text is sent to the browser
    informing that the document has moved (for those rare browsers that do not
    support redirection); this text can be overridden by supplying a text
    string.

    This function raises SERVER_RETURN exception with a value of state.DONE to
    ensuring that any later phases or stacked handlers do not run.
    """
    url = req.construct_url(uri)

    if permanent:
        req.status = HTTP_MOVED_PERMANENTLY
    else:
        req.status = HTTP_MOVED_TEMPORARILY

    req.headers_out.add('Location', url)
    req.content_type = 'plain/text'
    if text:
        req.write(text)
    raise SERVER_RETURN(DONE)
# enddef


def not_modified(req):
    req.status = HTTP_NOT_MODIFIED
    req.content_type = None
    return DONE


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
    req.log_error(traceback, LOG_ERR)
    traceback = traceback.split('\n')

    req.status = HTTP_INTERNAL_SERVER_ERROR
    if req.body_bytes_sent > 0:     # if body is sent
        return DONE

    req.__reset_buffer__()        # clean buffer for error text
    req.content_type = "text/html"
    req.headers_out = req.err_headers_out

    req.write(
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
        req.write(
            "  <h2> Exception Traceback</h2>\n"
            "  <pre>\n")

        # Traceback
        for i in xrange(len(traceback)):
            traceback_line = html_escape(traceback[i])
            req.write('<span class="line%s">%s</span>\n' %
                      (i % 2, traceback_line))

        req.write(
            "  </pre>\n"
            "  <hr>\n"
            "  <small><i>%s / Poor WSGI for Python ,webmaster: %s</i></small>"
            "\n" % (req.server_software, req.server_admin))
    else:
        req.write(
            "  <hr>\n"
            "  <small><i>webmaster: %s </i></small>\n" % req.server_admin)
    # endif

    req.write(
        " </body>\n"
        "</html>")

    return DONE
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

    req.content_type = "text/html"
    req.status = HTTP_BAD_REQUEST
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
# enddef


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

    req.content_type = "text/html"
    req.status = HTTP_FORBIDDEN
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
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

    req.content_type = "text/html"
    req.status = HTTP_NOT_FOUND
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
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

    req.content_type = "text/html"
    req.status = HTTP_METHOD_NOT_ALLOWED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
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
            "   status <code>%s</code>.</p>\n" % (req.uri, code))
        req.log_error('Your reqeuest %s returned not implemented status %d' %
                      (req.uri, code))
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

    req.content_type = "text/html"
    req.status = HTTP_NOT_IMPLEMENTED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
# enddef


def send_json(req, data, **kwargs):
    """Send data as application/json."""
    req.content_type = 'application/json'
    req._buffer = BytesIO(json_dumps(data, **kwargs))
    return DONE


def send_file(req, path, content_type=None):  # TODO: set content-length !!
    """Returns file with content_type as fast as possible on wsgi."""
    if content_type is None:     # auto mime type select
        (content_type, encoding) = mimetypes.guess_type(path)
    if content_type is None:     # default mime type
        content_type = "application/octet-stream"

    req.content_type = content_type

    if not access(path, R_OK):
        raise IOError("Could not stat file for reading")

    req._buffer = open(path, 'rb')
    return DONE
# enddef


def directory_index(req, _path):
    """
    Returns directory index as html page
    """
    if not path.isdir(_path):
        req.log_error(
            "Only directory_index can be send with directory_index handler. "
            "`%s' is not directory.",
            _path)
        raise SERVER_RETURN(HTTP_INTERNAL_SERVER_ERROR)

    index = listdir(_path)
    # parent directory
    if cmp(_path[:-1], req.document_root()) > 0:
        index.append("..")
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

        fpath = "%s/%s" % (_path, item)
        if not access(fpath, R_OK):
            continue

        fname = item + ('/' if path.isdir(fpath) else '')
        ftype = ""

        if path.isdir(fpath):
            ftype = "Directory"
        else:
            (ftype, encoding) = mimetypes.guess_type(fpath)
            if not ftype:
                ftype = 'application/octet-stream'
        # endif

        if path.isfile(fpath):
            size = "%.1f%s" % hbytes(path.getsize(fpath))
        else:
            size = "- "
        content += (
            "   <tr><td><a href=\"%s\">%s</a></td><td>%s</td>"
            "<td class=\"size\">%s</td><td>%s</td></tr>\n" %
            (diruri + '/' + fname,
             fname,
             strftime("%d-%b-%Y %H:%M", gmtime(path.getctime(fpath))),
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

    req.content_type = "text/html"
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
# enddef


def debug_info(req, app):
    # transform static handlers table to html
    shandlers_html = "<tr><th>Static:</th></tr>\n"
    shandlers_html += "\n".join(
        ('   <tr><td colspan="2"><a href="%s">%s</a></td>'
         '<td>%s</td><td>%s</td></tr>' %
         (u, u, human_methods_(m), f.__module__+'.'+f.__name__)
         for u, m, f in handlers_view(app.handlers)))

    # regular expression handlers
    rhandlers_html = "<tr><th>Regular expression:</th></tr>\n"
    rhandlers_html += "\n".join(
        ('   <tr><td><div class="path">%s</div></td>'
         '<td>%s</td><td>%s</td><td>%s</td></tr>' %
         (html_escape(u.pattern),
          ', '.join(tuple("%s:<b>%s</b>" % (G, C.__name__) for G, C in c)),
          human_methods_(m),
          f.__module__+'.'+f.__name__)
         for u, m, (f, c) in handlers_view(app.rhandlers, False)))

    dhandlers_html = "<tr><th>Default:</th></tr>\n"
    # this function could be called by user, so we need to test req.debug
    if req.debug and 'debug-info' not in app.handlers:
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
            for x, m, f in handlers_view({'x': app.dhandlers})))

    # transform state handlers and default state table to html, users handler
    # from shandlers are preferer
    _tmp_shandlers = {}
    _tmp_shandlers.update(default_shandlers)
    for k, v in app.shandlers.items():
        if k in _tmp_shandlers:
            _tmp_shandlers[k].update(app.shandlers[k])
        else:
            _tmp_shandlers[k] = app.shandlers[k]

    ehandlers_html = "\n".join(
        "   <tr><td>%s</td><td>%s</td><td>%s</td></tr>" %
        (c, human_methods_(m), f.__module__+'.'+f.__name__)
        for c, m, f in handlers_view(_tmp_shandlers))

    # pre and post table
    pre, post = app.pre, app.post
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
        (f, uni(r), c.__name__) for f, (r, c) in app.filters.items())

    # transform actual request headers to hml
    headers_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, uni(val)) for key, val in req.headers_in.items()))

    # transform some poor wsgi variables to html
    poor_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, uni(val)) for key, val in (
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
            ('Log Level', dict((b, a)
             for a, b in levels.items())[req._log_level]),
            ('Buffer Size', req._buffer_size),
            ('Document Root', req.document_root()),
            ('Document Index', req.document_index),
            ('Secret Key', '*'*5 + ' see in error output (wsgi log)'
             ' when Log Level is <b>debug</b> ' + '*'*5)
        )))
    req.log_error('SecretKey: %s' % repr(req.secret_key), LOG_DEBUG)

    # tranform application variables to html
    app_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, uni(val)) for key, val in req.get_options().items()))

    environ = req.environ.copy()
    environ['os.pgid'] = getgid()
    environ['os.puid'] = getuid()
    environ['os.egid'] = getegid()
    environ['os.euid'] = geteuid()

    # transfotm enviroment variables to html
    environ_html = "\n".join((
        "   <tr><td>%s:</td><td>%s</td></tr>" %
        (key, html_escape(uni(val))) for key, val in sorted(environ.items())))

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
            <a href="#uri_handlers">Uri handlers</a>
            <a href="#state_handlers">State handlers</a>
            <a href="#pre_post_handlers">Pre &amp; Post handlers</a>
            <a href="#filters">Filters</a>
            <a href="#headers">Headers</a>
            <a href="#poor_variables">Poor Variables</a>
            <a href="#app_variables">Aplication Variables</a>
            <a href="#environ">Environ</a>
          </nav>
          <h2 id="uri_handlers">Handlers Tanble</h2>
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

          <h2 id="pre_post_handlers">
            Pre process and Post process Handlers Tanble</h2>
          <table>
           <tr><th>Pre</th><th>Post</th></tr>
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
        </html>""") % (uni(shandlers_html),
                       uni(rhandlers_html),
                       uni(dhandlers_html),
                       uni(ehandlers_html),
                       uni(pre_post_html),
                       filters_html,           # some variable are unicode yet
                       headers_html,
                       poor_html,
                       app_html,
                       environ_html,
                       uni(req.server_software),
                       uni(req.server_admin))

    req.content_type = "text/html"
    req.write(content_html)
    return DONE
# enddef


def __fill_default_shandlers(code, handler):
    default_shandlers[code] = {}
    for m in methods.values():
        default_shandlers[code][m] = handler


__fill_default_shandlers(HTTP_NOT_MODIFIED, not_modified)
__fill_default_shandlers(HTTP_BAD_REQUEST, bad_request)
__fill_default_shandlers(HTTP_FORBIDDEN, forbidden)
__fill_default_shandlers(HTTP_NOT_FOUND, not_found)
__fill_default_shandlers(HTTP_METHOD_NOT_ALLOWED, method_not_allowed)
__fill_default_shandlers(HTTP_INTERNAL_SERVER_ERROR, internal_server_error)
__fill_default_shandlers(HTTP_NOT_IMPLEMENTED, not_implemented)
