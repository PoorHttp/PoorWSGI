#
# $Id: classes.py 32 2012-05-03 11:50:00Z ondratu $
#

from wsgiref.headers import Headers as WHeaders
from cgi import FieldStorage as CgiFieldStorage
from traceback import format_exception
from time import strftime, gmtime

import os, re, sys, mimetypes

if sys.version_info[0] < 3:
    from httplib import responses               # python 2.x
    from cStringIO import StringIO
else:
    from http.client import responses           # python 3.x
    from io import StringIO

from enums import *
from session import *

_httpUrlPatern = re.compile(r"^(http|https):\/\/")

## \defgroup http http server inetrface
# @{
#  Compatible as soon as posible with mod_python apache inteface.

class Headers(WHeaders):
    """Class inherited from wsgiref.headers.Headers."""

    def __init__(self):
        """By default constains X-Powered-By values."""
        headers = [
            ("X-Powered-By", "Poor WSGI for Python")
        ]
        WHeaders.__init__(self, headers)

    def add(self, key, value):
        """Set header key to value. Duplicate keys are not allowed."""
        if key != "Set-Cookie" and self.has_key(key):
            raise KeyError("Key %s exist." % key)
        self.add_header(key, value)
#endclass

class Request:
    """HTTP request object with all server elements. It could be compatible
        as soon as posible with mod_python.apache.request."""

    def __init__(self, environ, start_response):
        #apache compatibility

        self.environ = environ

        ## A table object containing environment information typically usable
        #  for CGI.
        self.subprocess_env = self.environ

        ## String. Host, as set by full URI or Host: header.
        self.hostname = self.environ.get('HTTP_HOST')

        ## A string containing the method - 'GET', 'HEAD', 'POST', etc. Same as
        #  CGI REQUEST_METHOD
        self.method = self.environ.get('REQUEST_METHOD')

        ## The path portion of the URI.
        self.uri = self.environ.get('PATH_INFO')

        ## String. The content type. Another way to set content_type is via
        #  headers_out object property.
        self.content_type = None

        self.clength = 0

        ## Status. One of http.enums.HTTP_* values.
        self.status = HTTP_OK

        ## A table object containing headers sent by the client.
        tmp = []
        for key, val in self.environ.items():
            if key[:5] == 'HTTP_':
                key = '-'.join(map(lambda x: x.capitalize() ,key[5:].split('_')))
                tmp.append((key, val))
            elif key in ("CONTENT_LENGTH", "CONTENT_TYPE"):
                key = '-'.join(map(lambda x: x.capitalize() ,key.split('_')))
                tmp.append((key, val))

        self.headers_in = WHeaders(tmp)

        ## A Headers object representing the headers to be sent to the client.
        self.headers_out = Headers()

        ## These headers get send with the error response, instead of headers_out.
        self.err_headers_out = Headers()

        ## uwsgi do not sent environ variables to apps environ
        if 'uwsgi.version' in self.environ or 'poor.Version' in os.environ:
            self.poor_environ = os.environ
        else:
            self.poor_environ = self.environ
        #endif

        ## String, which is used to encrypt http.session.PoorSession and
        #  http.session.Session

        self.secretkey = self.poor_environ.get(
                                'poor_SecretKey',
                                '$Id: env.py 30 2012-03-05 13:03:43Z ondratu $')

        self.debug = self.poor_environ.get('poor_Debug', 'Off').lower() == 'on'

        # @cond PRIVATE
        self.start_response = start_response
        self._start_response = False

        self._file = self.environ.get("wsgi.input")
        self._errors = self.environ.get("wsgi.errors")
        self._buffer = StringIO()
        self._buffer_len = 0
        self._buffer_offset = 0

        self.remote_host = self.environ.get('REMOTE_HOST')
        self.remote_addr = self.environ.get('REMOTE_ADDR')
        self.user_agent = self.environ.get('HTTP_USER_AGENT')
        self.scheme = self.environ.get('wsgi.url_scheme')

        self.server_software = self.environ.get('SERVER_SOFTWARE','Unknown')
        if self.server_software == 'Unknown' and 'uwsgi.version' in self.environ:
            self.server_software = 'uWsgi'
        self.server_admin = self.environ.get('SERVER_ADMIN',
                            'webmaster@%s' % self.hostname)

        # CGI SERVER NAME value (ServerName on apache)
        self.server_hostname = self.environ.get('SERVER_NAME')

        # Integer. TCP/IP port number. CGI SERVER PORT value
        self.port = self.environ.get('SERVER_PORT')

        # Protocol, as given by the client, or HTTP/0.9. cgi SERVER_PROTOCOL value
        self.protocol = self.environ.get('SERVER_PROTOCOL')

        try:
            self._log_level = levels[self.poor_environ.get('poor_LogLevel', 'warn').lower()]
        except:
            self._log_level = LOG_WARNING
            self.log_error('Bad poor_LogLevel, default is warn.', LOG_WARNING)
        #endtry

        try:
            self._buffer_size = int(self.poor_environ.get('poor_BufferSize', '8192'))
        except:
            self._buffer_size = 4096
            self.log_error('Bad poor_BufferSize, default is 8192.', LOG_WARNING)
        #endtry

        self.document_index = self.poor_environ.get('poor_DocumentIndex', 'Off').lower() == 'on'
        # @endcond
    #enddef

    def _read(self, length = -1):
        return self._file.read(length)

    def read(self, length = -1):
        """
        Read data from client (typical for XHR2 data POST). If length is not
        set, or if is lower then zero, Content-Length was be use.
        """
        content_length = int(self.headers_in.get("Content-Length", 0))
        if content_length == 0:
            self.log_error("No Content-Length found, read was failed!", LOG_ERR)
            return '';
        if length > -1 and length < content_length:
            self.read = self._read
            return self.read(length)
        return self._file.read(content_length)
    #enddef

    def write(self, data, flush = 0):
        """
        Write data to buffer. If len of data is bigger then poor_BufferSize,
        data was be sent to client via old write method (directly). Otherwhise,
        data was be sent at the end of request as iterable object.
        """
        # FIXME: self._buffer is not FIFO
        self._buffer_len += len(data)
        self._buffer.write(data)
        if self._buffer_len - self._buffer_offset > self._buffer_size:
            if not self._start_response:
                self._call_start_response()
            #endif
            self._buffer.seek(self._buffer_offset)
            self.__write(self._buffer.read(self._buffer_size))
            self._buffer_offset += self._buffer_size
            self._buffer.seek(0,2)  # seek to EOF
        if flush == 1:
            self.flush()
    #enddef

    def _call_start_response(self):
        if self.content_type and not self.headers_out.get('Content-Type'):
            self.headers_out.add('Content-Type', self.content_type)
        elif not self.content_type and not self.headers_out.get('Content-Type'):
            self.log_error('Content-type not set!', LOG_WARNING)

        if self.clength and not self.headers_out.get('Content-Length'):
            self.headers_out.add('Content-Length', str(self.clength))

        self.__write = self.start_response(
                            "%d %s" % (self.status, responses[self.status]),
                            self.headers_out.items())
        self._start_response = True
    #enddef

    def add_common_vars(self):
        """only set \b REQUEST_URI"""
        self.subprocess_env['REQUEST_URI'] = self.environ.get('PATH_INFO')

    def get_options(self):
        """Returns a reference to the ConfigParser object containing the
        server options."""
        options = {}
        for key,val in self.poor_environ.items():
            if key[:4].lower() == 'app_':
                options[key[4:].lower()] = val
        return options

    def get_remote_host(self):
        """Returns REMOTE_ADDR CGI enviroment variable."""
        return self.remote_addr

    def document_root(self):
        """Returns DocumentRoot setting."""
        self.log_error("poor_DocumentRoot: %s" % self.poor_environ.get('poor_DocumentRoot', ''),
                LOG_INFO)
        return self.poor_environ.get('poor_DocumentRoot', '')

    def construct_url(self, uri):
        """This function returns a fully qualified URI string from the path
        specified by uri, using the information stored in the request to
        determine the scheme, server host name and port. The port number is not
        included in the string if it is the same as the default port 80."""

        if not _httpUrlPatern.match(uri):
            return "%s://%s%s" % (self.scheme, self.hostname, uri)
        return uri
    #enddef

    def log_error(self, message, level = LOG_ERR, server = None):
        """An interface to the server http.classes.log.error method.
        @param message string with the error message
        @param level is one of the following flags constants:
        \code
        LOG_EMERG
        LOG_ALERT
        LOG_CRIT
        LOG_ERR
        LOG_WARNING
        LOG_NOTICE
        LOG_INFO
        LOG_DEBUG
        LOG_NOERRNO
        \endcode
        APLOG_constains are supported too for easier migration from mod_python.
        @param server interface only compatibility parameter
        """

        if self._log_level[0] >= level[0]:
            self._errors.write("<%s> %s\n" % (level[1], message))

    def __end_of_request__(self):
        if not self._start_response:
            self.set_content_lenght(self._buffer_len)
            self._call_start_response()
            self._buffer_offset = self._buffer_len
            self._buffer.seek(0)    # na zacatek !!
            return self._buffer     # return buffer (StringIO)
        else:
            self._buffer.seek(self._buffer_offset)
            self.__write(self._buffer.read())   # flush all from buffer
            self._buffer_offset = self._buffer_len
            return ()               # data was be sent via write method
        #enddef
    #enddef

    def flush(self):
        """Flushes the output buffer."""
        if not self._start_response:
            self._call_start_response()

        self._buffer.seek(self._buffer_offset)
        self.__write(self._buffer.read())       # flush all from buffer
        self._buffer_offset = self._buffer_len
    #enddef

    def sendfile(self, path, offset = 0, limit = -1 ):
        """
        Send file defined by path to client. offset and len is not supported yet
        """
        if not os.access(path, os.R_OK):
            raise IOError("Could not stat file for reading")

        length = 0

        bf = os.open(path, os.O_RDONLY)

        data = os.read(bf, self._buffer_size)
        while data != '':
            length += len(data)
            self.write(data)
            data = os.read(bf, self._buffer_size)
        #endwhile
        os.close(bf)

        return length
    #enddef

    def set_content_lenght(self, length):
        self.clength = length
    #enddef

#endclass

class FieldStorage(CgiFieldStorage):
    def __init__(self, fp_or_req = None,
                        headers = None,
                        outerboundary = '',
                        environ = os.environ,
                        keep_blank_values = 0,
                        strict_parsing = 0,
                        file_callback = None,
                        field_callback = None):

        self.environ = environ
        req = None
        if fp_or_req and isinstance(fp_or_req, Request):
            req = fp_or_req
            fp_or_req = None
            environ = req.environ

        if file_callback:
            environ['wsgi.file_callback'] = file_callback

        if req and req.method == 'POST':
            fp_or_req = environ.get('wsgi.input')

        CgiFieldStorage.__init__(
                    self,
                    fp = fp_or_req,
                    headers = headers,
                    outerboundary = outerboundary,
                    environ = environ,
                    keep_blank_values = keep_blank_values,
                    strict_parsing = strict_parsing)
    #enddef

    def make_file(self, binary = None):
        if 'wsgi.file_callback' in self.environ:
            return self.environ['wsgi.file_callback'](self.filename)
        else:
            return CgiFieldStorage.make_file(self, binary)
    #enddef

    def getfirst(self, name, default = None, fce = None):
        """Returns value of key from \b GET or \b POST form.
        @param name key
        @param default default value if is not set
        @param fce function which processed value. For example str or int
        """
        if fce:
            return fce(CgiFieldStorage.getfirst(self, name, default))
        return CgiFieldStorage.getfirst(self, name, default)
    #enddef

    def getlist(self, name, fce = None):
        """Returns list of values of key from \b GET or \b POST form.
        @param name key
        @param fce function which processed value. For example str or int
        """
        if fce:
            return map(fce, CgiFieldStorage.getlist(self, name))
        return CgiFieldStorage.getlist(self, name)
    #enddef

#endclass

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
    @param text plain text string
    @throw IOError
    """
    if len(req.headers_out) > 1 or 'X-Powered-By' not in req.headers_out:
        raise IOError('Headers are set before redirect')

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

## @}

## \defgroup internal Internal Poor Publisher functions and classes
#  @{

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
        "</html>" % (req.uri, req.server_admin)

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
        "</html>" % (req.uri, req.server_admin)

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
        "</html>" % (req.method, req.uri, req.server_admin)

    req.content_type = "text/html"
    req.status = HTTP_METHOD_NOT_ALLOWED
    req.headers_out = req.err_headers_out
    req.headers_out.add('Content-Length', str(len(content)))
    req.write(content)
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

    if not os.access(path, os.R_OK):
        raise IOError("Could not stat file for reading")

    #req._buffer = os.open(path, os.O_RDONLY)
    req._buffer = file(path, 'r')
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
        raise SERVER_RETURN(HTTP_INTERNAL_SERVER_ERROR)

    index = os.listdir(path)
    # parent directory
    if cmp(path[:-1], req.document_root()) > 0:
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

        fpath = "%s/%s" % (path, item)
        if not os.access(fpath, os.R_OK):
            continue

        fname = item + ('/' if os.path.isdir(fpath) else '')
        ftype = "";

        if os.path.isdir(fpath):
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
            strftime("%d-%b-%Y %H:%M", gmtime(os.path.getctime(fpath))),
            "%.1f%s" % hbytes(os.path.getsize(fpath)) if os.path.isfile(fpath) else "- ",
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

errors = {
    HTTP_INTERNAL_SERVER_ERROR  : internal_server_error,
    HTTP_NOT_FOUND              : not_found,
    HTTP_METHOD_NOT_ALLOWED     : method_not_allowed,
    HTTP_FORBIDDEN              : forbidden,
    HTTP_NOT_IMPLEMENTED        : not_implemented,
}

## @}
