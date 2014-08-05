"""
default Poor WSGI handlers
"""

from traceback import format_exception
from time import strftime, gmtime
from os import path, access, listdir, R_OK, getegid, geteuid, getuid, getgid
from operator import itemgetter
from sys import version_info, version, exc_info

import mimetypes

if version_info[0] < 3:      # python 2.x
    from httplib import responses
else:                           # python 3.x
    from http.client import responses
    xrange = range

from poorwsgi.state import __author__, __date__, __version__, \
        DONE, METHOD_ALL, methods, sorted_methods, levels, LOG_ERR, \
        HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY, HTTP_FORBIDDEN, \
        HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED, HTTP_INTERNAL_SERVER_ERROR, \
        HTTP_NOT_IMPLEMENTED

class SERVER_RETURN(Exception):
    """Compatible with mod_python.apache exception."""
    def __init__(self, code = HTTP_INTERNAL_SERVER_ERROR):
        """code is one of HTTP_* status from state module"""
        Exception.__init__(self, code)
#endclass

def redirect(req, uri, permanent = 0, text = None):
    """This is a convenience function to redirect the browser to another
    location. When permanent is true, MOVED_PERMANENTLY status is sent to the
    client, otherwise it is MOVED_TEMPORARILY. A short text is sent to the
    browser informing that the document has moved (for those rare browsers that
    do not support redirection); this text can be overridden by supplying a text
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
#enddef

def internal_server_error(req):
    """ More debug 500 Internal Server Error server handler. It was be called
        automaticly when no handlers are not defined in dispatch_table.errors.
        If poor_Debug variable is to On, Tracaback will be genarated.
    """
    exc_type, exc_value, exc_traceback = exc_info()
    traceback = format_exception(exc_type,
                                 exc_value,
                                 exc_traceback)
    traceback = ''.join(traceback)
    req.log_error(traceback, LOG_ERR)
    traceback = traceback.split('\n')

    req.status = HTTP_INTERNAL_SERVER_ERROR
    if req.body_bytes_sent > 0: # if body is sent
        return DONE

    req.__reset_buffer__()        # clean buffer for error text
    req.content_type = "text/html"
    req.headers_out = req.err_headers_out

    content = [
            "<html>\n",
            "  <head>\n",
            "    <title>500 - Internal Server Error</title>\n",
            "    <style>\n",
            "      body {width: 80%; margin: auto; padding-top: 30px;}\n",
            "      h1 {text-align: center; color: #707070;}\n"\
            "      pre .line1 {background: #e0e0e0}\n",
            "    </style>\n",
            "  <head>\n",
            "  <body>\n",
            "    <h1>500 - Internal Server Error</h1>\n",
    ]
    for l in content: req.write(l)

    if req.debug:
        content = [
            "    <h2> Exception Traceback</h2>\n",
            "    <pre>",
        ]
        for l in content: req.write(l)

        # Traceback
        for i in xrange(len(traceback)):
            req.write('<div class="line%s">%s</div>' % ( i % 2, traceback[i]))

        content = [
            "    </pre>\n",
            "    <hr>\n",
            "    <small><i>%s / Poor WSGI for Python , webmaster: %s </i></small>\n" % \
                    (req.server_software,
                    req.server_admin),
        ]
        for l in content: req.write(l)

    else:
        content = [
            "    <hr>\n",
            "    <small><i>webmaster: %s </i></small>\n" % req.server_admin ,
        ]
        for l in content: req.write(l)
    #endif

    content = [
        "  </body>\n",
        "</html>"
    ]

    for l in content: req.write(l)
    return DONE
#enddef

def forbidden(req):
    """ 403 - Forbidden Access server error handler. """
    content = \
        "<html>\n"\
        "  <head>\n"\
        "    <title>403 - Forbidden Acces</title>\n"\
        "    <style>\n"\
        "      body {width: 80%%; margin: auto; padding-top: 30px;}\n"\
        "      h1 {text-align: center; color: #ff0000;}\n"\
        "      p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"\
        "    </style>\n"\
        "  <head>\n" \
        "  <body>\n"\
        "    <h1>403 - Forbidden Access</h1>\n"\
        "    <p>You don't have permission to access <code>%s</code> on this server.</p>\n"\
        "    <hr>\n"\
        "    <small><i>webmaster: %s </i></small>\n"\
        "  </body>\n"\
        "</html>" % (req.uri, req.server_admin)

    req.content_type = "text/html"
    req.status = HTTP_FORBIDDEN
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef


def not_found(req):
    """ 404 - Page Not Found server error handler. """
    content = \
        "<html>\n"\
        "  <head>\n"\
        "    <title>404 - Page Not Found</title>\n"\
        "    <style>\n"\
        "      body {width: 80%%; margin: auto; padding-top: 30px;}\n"\
        "      h1 {text-align: center; color: #707070;}\n"\
        "      p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"\
        "    </style>\n"\
        "  <head>\n" \
        "  <body>\n"\
        "    <h1>404 - Page Not Found</h1>\n"\
        "    <p>Your reqeuest <code>%s</code> was not found.</p>\n"\
        "    <hr>\n"\
        "    <small><i>webmaster: %s </i></small>\n"\
        "  </body>\n"\
        "</html>" % (req.uri, req.server_admin)

    req.content_type = "text/html"
    req.status = HTTP_NOT_FOUND
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def method_not_allowed(req):
    """ 405 Method Not Allowed server error handler. """
    content = \
        "<html>\n"\
        "  <head>\n"\
        "    <title>405 - Method Not Allowed</title>\n"\
        "    <style>\n"\
        "      body {width: 80%%; margin: auto; padding-top: 30px;}\n"\
        "      h1 {text-align: center; color: #707070;}\n"\
        "      p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"\
        "    </style>\n"\
        "  <head>\n"\
        "  <body>\n"\
        "    <h1>405 - Method Not Allowed</h1>\n"\
        "    <p>This method %s is not allowed to access <code>%s</code> on this server.</p>\n"\
        "    <hr>\n"\
        "    <small><i>webmaster: %s </i></small>\n"\
        "  </body>\n"\
        "</html>" % (req.method, req.uri, req.server_admin)

    req.content_type = "text/html"
    req.status = HTTP_METHOD_NOT_ALLOWED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def not_implemented(req, code = None):
    """ 501 Not Implemented server error handler. """
    content = \
            "<html>\n"\
            "  <head>\n"\
            "    <title>501 - Not Implemented</title>\n"\
            "    <style>\n"\
            "      body {width: 80%%; margin: auto; padding-top: 30px;}\n"\
            "      h1 {text-align: center; color: #707070;}\n"\
            "      p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n"\
            "    </style>\n"\
            "  <head>\n"\
            "  <body>\n"\
            "    <h1>501 - Not Implemented</h1>\n"

    if code:
        content += \
            "    <p>Your reqeuest <code>%s</code> returned not implemented\n"\
            "      status <code>%s</code>.</p>\n" % (req.uri, code)
    else:
        content += \
            "    <p>Response for Your reqeuest <code>%s</code> is not implemented</p>" \
            % req.uri
    #endif

    content += \
            "    <hr>\n"\
            "    <small><i>webmaster: %s </i></small>\n"\
            "  </body>\n"\
            "</html>" % req.server_admin

    req.content_type = "text/html"
    req.status = HTTP_NOT_IMPLEMENTED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def send_file(req, path, content_type = None):
    """
    Returns file with content_type as fast as possible on wsgi
    """
    if content_type == None:     # auto mime type select
        (content_type, encoding) = mimetypes.guess_type(path)
    if content_type == None:     # default mime type
        content_type = "application/octet-stream"

    req.content_type = content_type

    if not access(path, R_OK):
        raise IOError("Could not stat file for reading")

    req._buffer = open(path, 'rb')
    return DONE
#enddef

def directory_index(req, _path):
    """
    Returns directory index as html page
    """
    if not path.isdir(_path):
        req.log_error (
            "Only directory_index can be send with directory_index handler. "
            "`%s' is not directory.",
            _path);
        raise SERVER_RETURN(HTTP_INTERNAL_SERVER_ERROR)

    index = listdir(_path)
    # parent directory
    if cmp(_path[:-1], req.document_root()) > 0:
        index.append("..")
    index.sort()

    def hbytes(val):
        unit = ' '
        if val > 100:
            unit = 'k'
            val = val / 1024.0
        if val > 500:
            unit = 'M'
            val = val / 1024.0
        if val > 500:
            unit = 'G'
            val = val / 1024.0
        return (val, unit)
    #enddef

    diruri = req.uri.rstrip('/')
    content = [
        "<html>\n",
        "  <head>\n",
        "    <title>Index of %s</title>\n" % diruri,
        "    <meta http-equiv=\"content-type\" content=\"text/html; charset=utf-8\"/>\n",
        "    <style>\n",
        "      body { width: 98%; margin: auto; }\n",
        "      table { font: 90% monospace; text-align: left; }\n",
        "      td, th { padding: 0 1em 0 1em; }\n",
        "      .size { text-align:right; white-space:pre; }\n",
        "    </style>\n",
        "  <head>\n",
        "  <body>\n",
        "    <h1>Index of %s</h1>\n" % diruri,
        "    <hr>\n"
        "    <table>\n",
        "      <tr><th>Name</th><th>Last Modified</th>"
                  "<th class=\"size\">Size</th><th>Type</th></tr>\n"
    ]

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
        ftype = "";

        if path.isdir(fpath):
            ftype = "Directory"
        else:
            (ftype, encoding) = mimetypes.guess_type(fpath)
            if not ftype:
                ftype = 'application/octet-stream'
        #endif

        content.append("      "
            "<tr><td><a href=\"%s\">%s</a></td><td>%s</td>"
            "<td class=\"size\">%s</td><td>%s</td></tr>\n" %\
            (diruri + '/' + fname,
            fname,
            strftime("%d-%b-%Y %H:%M", gmtime(path.getctime(fpath))),
            "%.1f%s" % hbytes(path.getsize(fpath)) if path.isfile(fpath) else "- ",
            ftype
            ))

    content += [
        "    </table>\n",
        "    <hr>\n"
    ]

    if req.debug:
        content += [
            "    <small><i>%s / Poor WSGI for Python, webmaster: %s </i></small>\n" % \
                    (req.server_software,
                    req.server_admin),
        ]
    else:
        content += [
            "    <small><i>webmaster: %s </i></small>\n" % req.server_admin
        ]

    content += [
        "  </body>\n",
        "</html>"
    ]

    req.content_type = "text/html"
    #req.headers_out.add('Content-Length', str(len(content)))
    for l in content: req.write(l)
    return DONE
#enddef

def debug_info(req, app):
    def _human_methods_(m):
        if m == METHOD_ALL:
            return 'ALL'
        return ' | '.join(key for key, val in sorted_methods if val & m)
    #enddef

    def _html_escape_(s):
        s = s.replace('&', '&amp;')
        s = s.replace('>', '&gt;')
        s = s.replace('<', '&lt;')
        return s
    #enddef

    def handlers_view(handlers, sort = True):
        rv = []
        for u, d in sorted(handlers.items()) if sort else handlers.items():
            mm = sorted(d.keys()) if sort else d.keys()

            vt = {}
            for m, h in d.items():
                if not h in vt: vt[h] = 0
                vt[h] ^= m

            for h,m in sorted(vt.items(), key = itemgetter(1)):
                rv.append((u, m, h))

        return rv
    #enddef

    # transform handlers table to html
    handlers_html  = "\n<tr><th>Static:</th></tr>"
    handlers_html += "\n".join(
            ("        <tr><td colspan=\"2\"><a href=\"%s\">%s</a></td><td>%s</td><td>%s</td></tr>" % \
                (u, u, _human_methods_(m), f.__module__+'.'+f.__name__) \
                    for u, m, f in handlers_view(app.handlers) ))

    handlers_html += "\n<tr><th>Regular expression:</th></tr>"
    # regular expression handlers
    handlers_html += "\n".join(
            ("        <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % \
                (_html_escape_(u.pattern), ', '.join(tuple("%s:<b>%s</b>" % (G, C.__name__) for G,C in c)), _human_methods_(m), f.__module__+'.'+f.__name__) \
                    for u, m, (f, c) in handlers_view(app.rhandlers, False) ))

    handlers_html += "\n<tr><th>Default:</th></tr>"
    # this result function could be called by user, so we need to test req.debug
    if req.debug and 'debug-info' not in app.handlers:
        handlers_html += "        <tr><td colspan=\"2\"><a href=\"%s\">%s</a></td><td>%s</td><td>%s</td></tr>" % \
            ('/debug-info', '/debug-info', 'ALL', debug_info.__module__+'.'+debug_info.__name__ )

    handlers_html += "\n".join(
            ("        <tr><td colspan=\"2\">_default_handler_</td><td>%s</td><td>%s</td></tr>" % \
                (_human_methods_(m), f.__module__+'.'+f.__name__) \
                    for x, m, f in handlers_view({'x': app.dhandlers}) ))

    # transform state handlers and default state table to html, users handler
    # from shandlers are preferer 
    _tmp_shandlers = {}
    _tmp_shandlers.update(default_shandlers)
    for k, v in app.shandlers.items():
        if k in _tmp_shandlers:
            _tmp_shandlers[k].update(app.shandlers[k])
        else:
            _tmp_shandlers[k] = app.shandlers[k]
    #endfor
    ehandlers_html = "\n".join("        <tr><td>%s</td><td>%s</td><td>%s</td></tr>" % \
                (c, _human_methods_(m), f.__module__+'.'+f.__name__) \
                    for c, m, f in handlers_view(_tmp_shandlers))

    # pre and post table
    pre, post = app.pre, app.post
    if len(pre) >= len(post):
        post += (len(pre)-len(post)) * (None, )
    else:
        pre += (len(post)-len(pre)) * (None, )

    pre_post_html = "\n".join("        <tr><td>%s</td><td>%s</td></tr>" % \
                (f0.__module__+'.'+f0.__name__ if f0 is not None else '',
                 f1.__module__+'.'+f1.__name__ if f1 is not None else '',) \
                    for f0, f1 in zip(pre, post))

    # filters
    filters_html = "\n".join("        <tr><td>%s</td><td>%s</td><td>%s</td></tr>" % \
                (f, str(r), c.__name__) for f, (r, c) in app.filters.items() )

    # transform actual request headers to hml
    headers_html = "\n".join(("        <tr><td>%s:</td><td>%s</td></tr>" %\
                    (key, val) for key, val in req.headers_in.items()))

    # transform some poor wsgi variables to html
    poor_html = "\n".join(("        <tr><td>%s:</td><td>%s</td></tr>" %\
            (key, val) for key, val in (
                    ('SecretKey', req.secretkey),
                    ('Debug', req.debug),
                    ('Version', "%s (%s)" % (__version__, __date__)),
                    ('Python Version', version),
                    ('Server Software', req.server_software),
                    ('Server Hostname', req.server_hostname),
                    ('Server Port', req.port),
                    ('Server Admin', req.server_admin),
                    ('Log Level', dict((b,a) for a,b in levels.items())[req._log_level]),
                    ('Buffer Size', req._buffer_size),
                    ('Document Root', req.document_root()),
                    ('Document Index', req.document_index)
        )))

    # tranform application variables to html
    app_html = "\n".join(("        <tr><td>%s:</td><td>%s</td></tr>" %\
                    (key, val) for key, val in req.get_options().items()))

    environ = req.environ.copy()
    environ['os.pgid'] = getgid()
    environ['os.puid'] = getuid()
    environ['os.egid'] = getegid()
    environ['os.euid'] = geteuid()

    # transfotm enviroment variables to html
    environ_html = "\n".join(("        <tr><td>%s:</td><td>%s</td></tr>" %\
                    (key, str(val)) for key,val in sorted(environ.items())))


    content_html = \
"""<html>
  <head>
    <title>Poor Wsgi Debug info</title>
    <meta http-equiv=\"content-type\" content=\"text/html; charset=utf-8\"/>
    <style>
      body { width: 80%%; margin: auto; padding-top: 30px; }
      h1 { text-align: center; color: #707070; }
      h2 { font-family: monospace; }
      table { width: 100%%; font-family: monospace; }
      table tr:nth-child(odd) { background: #e0e0e0; }
      th { padding: 10px 4px 0; text-align: left; background: #fff; }
      td { word-break:break-word; }
      td:first-child { white-space: nowrap; word-break:keep-all; }
    </style>
  <head>
    <body>
      <h1>Poor Wsgi Debug Info</h1>
      <h2>Handlers Tanble</h2>
      <table>%s</table>
      <h2>Http State Handlers Tanble</h2>
      <table>%s</table>
      <h2>Pre process and Post process Handlers Tanble</h2>
      <table>
        <tr><th>Pre</th><th>Post</th></tr>
      %s</table>
      <h2>Routing regular expression filters</h2>
      <table>%s</table>
      <h2>Request Headers</h2>
      <table>%s</table>
      <h2>Poor Request variables <small>(with <code>poor_</code> prefix)</small></h2>
      <table>%s</table>
      <h2>Application variables <small>(with <code>app_</code> prefix)</small></h2>
      <table>%s</table> 
      <h2>Request Environ</h2>
      <table style="font-size: 90%%;">%s</table>
      <hr>
      <small><i>%s / Poor WSGI for Python , webmaster: %s </i></small>
    </body>
</html>""" % (
        handlers_html,
        ehandlers_html,
        pre_post_html,
        filters_html,
        headers_html,
        poor_html,
        app_html,
        environ_html,
        req.server_software,
        req.server_admin
    )

    req.content_type = "text/html"
    req.write(content_html)
    return DONE
#enddef

# http state handlers, which is called if programmer don't defined his own
default_shandlers = {}

def __fill_default_shandlers(code, handler):
    default_shandlers[code] = {}
    for m in methods.values():
        default_shandlers[code][m] = handler

__fill_default_shandlers(HTTP_INTERNAL_SERVER_ERROR, internal_server_error)
__fill_default_shandlers(HTTP_NOT_FOUND, not_found)
__fill_default_shandlers(HTTP_METHOD_NOT_ALLOWED, method_not_allowed)
__fill_default_shandlers(HTTP_FORBIDDEN, forbidden)
__fill_default_shandlers(HTTP_NOT_IMPLEMENTED, not_implemented)

