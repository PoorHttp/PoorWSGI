
from random import random
from time import localtime, strftime, gmtime
from traceback import format_exception
from os import name as osname
#
# $Id$
#

from exceptions import IOError
import types, sys, os

from enums import *
import env

## \addtogroup <http>
#  @{


class SERVER_RETURN(Exception):
    """Compatible with mod_python.apache exception."""
    def __init__(self, code = HTTP_INTERNAL_SERVER_ERROR):
        """@param code one of HTTP_* status from http.enums"""
        Exception.__init__(self, code)
#endclass

def redirect(req, uri, permanent = 0, text = None):
    """This is a convenience function to redirect the browser to another
    location. When permanent is true, MOVED_PERMANENTLY status is sent to the
    client, otherwise it is MOVED_TEMPORARILY. A short text is sent to the
    browser informing that the document has moved (for those rare browsers that
    do not support redirection); this text can be overridden by supplying a text
    string. 

    If this function is called after the headers have already been sent, an
    IOError is raised. 

    This function raises apache.SERVER_RETURN exception with a value of
    http.DONE to ensuring that any later phases or stacked handlers do not run.
    If you do not want this, you can wrap the call to redirect in a try/except
    block catching the apache.SERVER_RETURN. Redirect server request to url via
    302 server status.

    @param req http.classes.Request object
    @param uri string location
    @param permanent int or boolean
    @param text string
    @throw IOError
    """
    if len(req.headers_out) > 2 or \
        'Server' not in req.headers_out or 'X-Powered-By' not in req.headers_out:
        raise IOError('Headers are set before redirect')
    
    url = req.construct_url(uri)
    
    if permanent:
        req.status = HTTP_MOVED_PERMANENTLY
    else:
        req.status = HTTP_MOVED_TEMPORARILY
    
    req.headers_out.add('Location', url)
    if text:
        req.write(text)
    raise SERVER_RETURN, DONE
#enddef

## @}

## \defgroup internal Internal Poor Publisher functions and classes
#  @{

def forbidden(req):
    """403 - Forbidden Access server error handler.
    @param req http.classes.Request object
    @returns http.DONE
    """
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
        "</html>" % (req.uri, env.webmaster)
        
    req.content_type = "text/html"
    req.status = HTTP_FORBIDDEN
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def not_found(req):
    """404 - Page Not Found server error handler.
    @param req http.classes.Request object
    @returns http.DONE
    """
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
        "</html>" % (req.uri, env.webmaster)
        
    req.content_type = "text/html"
    req.status = HTTP_NOT_FOUND
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def method_not_allowed(req):
    """405 Method Not Allowed server error handler.
    @param req http.classes.Request object
    @returns http.DONE
    """
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
        "</html>" % (req.method, req.uri, env.webmaster)
        
    req.content_type = "text/html"
    req.status = HTTP_METHOD_NOT_ALLOWED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def internal_server_error(req):
    """More debug 500 Internal Server Error server handler. It was be called
    automaticly when no handlers are not defined in dispatch_table.errors.
    If __debug__ is true, Tracaback will be genarated.
    @param req http.classes.Request object
    @returns http.DONE
    """
    traceback = format_exception(sys.exc_type,
                                 sys.exc_value,
                                 sys.exc_traceback)
    traceback = ''.join(traceback)
    req.log_error(traceback, LOG_ERR)
    traceback = traceback.split('\n')

    req.content_type = "text/html"
    req.status = HTTP_INTERNAL_SERVER_ERROR
    req.headers_out = req.err_headers_out

    content = [
            "<html>\n",
            "  <head>\n",
            "    <title>500 - Internal Server Error</title>\n",
            "    <style>\n",
            "      body {width: 80%%; margin: auto; padding-top: 30px;}\n",
            "      pre .line1 {background: #e0e0e0}\n",
            "    </style>\n",
            "  <head>\n",
            "  <body>\n",
            "    <h1>500 - Internal Server Error</h1>\n",
    ]
    for l in content: req.write(l)

    if env.debug:
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
            "    <small><i>Poor Http / %s, Python / %s, webmaster: %s </i></small>\n" % \
                    (env.server_version,
                    sys.version.split(' ')[0],
                    env.webmaster),
        ]
        for l in content: req.write(l)
    
    else:
        content = [
            "    <hr>\n",
            "    <small><i>webmaster: %s </i></small>\n" % env.webmaster ,
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

def not_implemented(req, code = None):
    """501 Not Implemented server error handler.
    @param req http.classes.Request object
    @returns http.DONE
    """
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
            "</html>" % env.webmaster
        
    req.content_type = "text/html"
    req.status = HTTP_NOT_IMPLEMENTED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
    return DONE
#enddef

def send_file(req, path):
    """
    Returns file with content_type detect from server configuration or
    application/octet-stream.
    """
    
    ext = os.path.splitext(path)
    if env.cfg.has_option('mime-type', ext[1][1:]):
        req.content_type = env.cfg.get('mime-type', ext[1][1:])
    else:
        req.content_type = 'application/octet-stream'
    #endif

    #bf = os.open(path, os.O_RDONLY)
    #req.headers_out.add('Content-Disposition',
    #        'attachment; filename="%s"' % os.path.basename(path))
    #req.headers_out.add('Content-Length', str(os.fstat(bf).st_size))
    
    req.sendfile(path)

    return DONE
#enddef

def directory_index(req, path):
    """
    Returns directory index as html page
    """
    if not os.path.isdir(path):
        req.log_error (
            "Only directory_index can be send with directory_index handler. "
            "`%s' is not directory.",
            path);
        raise SERVER_RETURN, HTTP_INTERNAL_SERVER_ERROR
    
    index = os.listdir(path)
    # parent directory
    if cmp(path[:-1], env.document_root) > 0:
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

    content = [
        "<html>\n",
        "  <head>\n",
        "    <title>Index of %s</title>\n" % req.uri,
        "    <meta http-equiv=\"content-type\" content=\"text/html; charset=utf-8\"/>\n",
        "    <style>\n",
        "      body { width: 98%; margin: auto; }\n",
        "      table { font: 90% monospace; text-align: left; }\n",
        "      td, th { padding: 0 1em 0 1em; }\n",
        "      .size { text-align:right; white-space:pre; }\n",
        "    </style>\n",
        "  <head>\n",
        "  <body>\n",
        "    <h1>Index of %s</h1>\n" % req.uri,
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

        fpath = "%s/%s" % (path, item)
        fname = item + ('/' if os.path.isdir(fpath) else '')
        ftype = "";
        if os.path.isdir(fpath):
            ftype = "Directory"
        else:
            ext = os.path.splitext(item)
            if env.cfg.has_option('mime-type', ext[1][1:]):
                ftype = env.cfg.get('mime-type', ext[1][1:])
            else:
                ftype = 'application/octet-stream'
        #endif

        content.append("      "
            "<tr><td><a href=\"%s\">%s</a></td><td>%s</td>"
            "<td class=\"size\">%s</td><td>%s</td></tr>\n" %\
            (fname,
            "Parent Directory" if fname == "../" else fname,
            strftime("%d-%b-%Y %H:%M", gmtime(os.path.getctime(fpath))),
            "%.1f%s" % hbytes(os.path.getsize(fpath)) if os.path.isfile(fpath) else "- ",
            ftype
            ))

    content += [
        "    </table>\n",
        "    <hr>\n"
    ]

    if env.debug:
        content += [
            "    <small><i>Poor Http / %s, Python / %s, webmaster: %s </i></small>\n" % \
                    (env.server_version,
                    sys.version.split(' ')[0],
                    env.webmaster),
        ]
    else:
        content += [
            "    <small><i>webmaster: %s </i></small>\n" % env.webmaster
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

errors = {
    HTTP_INTERNAL_SERVER_ERROR  : internal_server_error,
    HTTP_NOT_FOUND              : not_found,
    HTTP_METHOD_NOT_ALLOWED     : method_not_allowed,
    HTTP_FORBIDDEN              : forbidden,
    HTTP_NOT_IMPLEMENTED        : not_implemented,
}

## @{
