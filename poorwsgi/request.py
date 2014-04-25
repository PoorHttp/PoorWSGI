"""
Headers, Request and FieldStorage classes, which is used for managing requests.
"""


from wsgiref.headers import Headers as WHeaders
from cgi import FieldStorage as CgiFieldStorage
from time import strftime, gmtime
from sys import version_info, stderr
from inspect import stack

import os, re

if version_info.major < 3:      # python 2.x
    from httplib import responses
    from cStringIO import StringIO as BytesIO
    from urlparse import parse_qs

    _unicode_exist = True
else:                           # python 3.x
    from http.client import responses
    from io import BytesIO
    from urllib.parse import parse_qs

    _unicode_exist = False

from poorwsgi.state import __author__, __date__, __version__, methods, \
        levels, LOG_ERR, LOG_WARNING, LOG_INFO, \
        METHOD_POST, METHOD_PUT, METHOD_PATCH, \
        HTTP_OK, \
        HTTP_INTERNAL_SERVER_ERROR

from poorwsgi.results import SERVER_RETURN as SERVER_RETURN_RIGHT

# simple regular expression for construct_url method
_httpUrlPatern = re.compile(r"^(http|https):\/\/")

if _unicode_exist:
    def uni(text):
        """ automatic conversion from str to unicode with utf-8 encoding """
        if isinstance(text, str):
            return unicode(text, encoding = 'utf-8')
        return unicode(text)
else:
    def uni(text):
        """ automatic conversion from str to unicode with utf-8 encoding """
        return str(text)


class Headers(WHeaders):
    """Class inherited from wsgiref.headers.Headers."""

    def __init__(self):
        """By default constains X-Powered-By values."""
        headers = [
            ("X-Powered-By", "Poor WSGI for Python")
        ]
        WHeaders.__init__(self, headers)

    def add(self, key, value):
        """ Set header key to value. Duplicate keys are not allowed instead of
            {Set-Cookie}.
        """
        if key != "Set-Cookie" and key in self:
            raise KeyError("Key %s exist." % key)
        self.add_header(key, value)
#endclass

class Request:
    """ HTTP request object with all server elements. It could be compatible
        as soon as possible with mod_python.apache.request.

        Instance has these information variables for reading:
            environ         - a table object containing request environment information
                             from wsgi server.
            subprocess_env  - apache compatible variable for environ
            scheme          - request scheme, typical {http} or {https}
            hostname        - string. Host, as set by full URI or Host: header.
            port            - server port
            protocol        - server protocol
            remote_host     - remote hostname
            remote_addr     - remote address
            referer         - request referer if is available or None
            user_agent      - browser user agent string
            server_hostname - server name variable
            server_software - server software
            server_admin    - server admin if set, or webmaster@hostname
            poor_environ    - environ with poor_ variables. It is environ from
                             request, or os.environ
            document_index  - value of poor_DocumentIndex variable, which is used
                             to generate index html page, when poor_DocumentRoot
                             is set.
            debug           - value of poor_Debug variable
            secretkey       - value of poor_SecretKey variable, which is used for
                             PoorSession class.
            method          - a string containing the method - {GET}, {HEAD},
                             {POST}, etc.
            method_number   - method number constant from state module
            uri             - the path portion of the URI.
            uri_rule        - Rule from one of application handler table.
            headers_in      - input headers object
            is_xhr          - If X-Requested-With header is set and have
                             XMLHttpRequest value, then is true.
            headers_out     - output headers object
            err_headers_out - output headers object for error pages.
            args            - extended dictionary (Args instance) of request
                             arguments from QUERY_STRING, which is typical, but
                             not only for GET method. Arguments are parsed when
                             poor_AutoArgs is set which is default.
            forms           - dictionary like class (FieldStorage instance) of
                             method arguments which are send in request body,
                             which is typical for POST, PUT or PATCH method.
                             Request body is parsed when poor_AutoForm is set
                             which default and when method is POST, PUT or PATCH.
            clength         - variable to store output content length. To set this
                             variable, use set_content_lenght method.
            body_bytes_sent - internal variable to store count of bytes which are
                             really sent to wsgi server.

        Only two variables for writing.
            content_type    - String. The content type. Another way to set
                             content_type is via headers_out object property.
                             Default is *{ text/html; charset=utf-8 }*
            status          - http status code, which is state.HTTP_OK (200) by
                             default. If you want to set this variable (which
                             is very good idea in http_state handlers), it is
                             good solution to use some of HTTP_ constant from
                             state module.

        Special variables for user use:
            config          - for config object (default None)
            logger          - for special logger object or logger function
                              (default req.log_error)
            user            - for user object, who is login for example (default
                              None)
            app_            - as prefix for any your application variable (not
                              defined)

    """

    def __init__(self, environ, start_response, app_config):
        """ Object was created automatically in wsgi module. It's input parameters
            are the same, which Application object gets from WSGI server plus
            file callback for auto request body parsing.
        """
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
        if not self.method in methods:
            self.method = 'HEAD'

        self.method_number = methods[self.method]

        ## The path portion of the URI.
        self.uri = uni(self.environ.get('PATH_INFO'))
        self.uri_rule = None

        ## String. The content type. Another way to set content_type is via
        #  headers_out object property. Default is text/html; charset=utf-8
        self.content_type = "text/html; charset=utf-8"

        self.clength = 0

        self.body_bytes_sent = 0

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
        self.is_xhr = (self.headers_in.get('X-Requested-With','XMLHttpRequest') == 'XMLHttpRequest')

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

        ## args
        if app_config['auto_args']:
            self.args = Args(self, app_config['keep_blank_values'],
                                   app_config['strict_parsing'])
        else: self.args = EmptyForm()

        if app_config['auto_form'] and self.method_number & (METHOD_POST | METHOD_PUT | METHOD_PATCH):
            self.form = FieldStorage(self,
                            keep_blank_values = app_config['keep_blank_values'],
                            strict_parsing = app_config['strict_parsing'])
        else: self.form = EmptyForm()

        self.debug = self.poor_environ.get('poor_Debug', 'Off').lower() == 'on'

        self.start_response = start_response
        self._start_response = False

        self._file = self.environ.get("wsgi.input")
        self._errors = self.environ.get("wsgi.errors")
        self._buffer = BytesIO()
        self._buffer_len = 0
        self._buffer_offset = 0

        self.remote_host = self.environ.get('REMOTE_HOST')
        self.remote_addr = self.environ.get('REMOTE_ADDR')
        self.referer = self.environ.get('HTTP_REFERER', None)
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
        self.port = int(self.environ.get('SERVER_PORT'))

        # Protocol, as given by the client, or HTTP/0.9. cgi SERVER_PROTOCOL value
        self.protocol = self.environ.get('SERVER_PROTOCOL')

        # String, which is used to encrypt session.PoorSession
        self.secretkey = self.poor_environ.get(
                'poor_SecretKey',
                'Poor WSGI/%s for Python/%s.%s on %s' % \
                    (__version__, version_info[0], version_info[1],
                    self.server_software))

        try:
            self._log_level = levels[self.poor_environ.get('poor_LogLevel', 'warn').lower()]
        except:
            self._log_level = LOG_WARNING
            self.log_error('Bad poor_LogLevel, default is warn.', LOG_WARNING)
        #endtry

        try:
            self._buffer_size = int(self.poor_environ.get('poor_BufferSize', '16384'))
        except:
            self._buffer_size = 16384
            self.log_error('Bad poor_BufferSize, default is 16384 B (16 KiB).', LOG_WARNING)
        #endtry

        self.document_index = self.poor_environ.get('poor_DocumentIndex', 'Off').lower() == 'on'

        ### variables for user use
        self.config = None
        self.logger = self.log_error
        self.user = None
    #enddef

    def __read(self, length = -1):
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
            self.read = self.__read
            return self.read(length)
        return self._file.read(content_length)
    #enddef

    def write(self, data, flush = 0):
        """
        Write data to buffer. If len of data is bigger then poor_BufferSize,
        data was be sent to client via old write method (directly). Otherwhise,
        data was be sent at the end of request as iterable object.
        """
        if (not _unicode_exist and isinstance(data, str)) or \
            (_unicode_exist and isinstance(data, unicode)):
            data = data.encode('utf-8')

        # FIXME: self._buffer is not FIFO
        self._buffer_len += len(data)
        self._buffer.write(data)
        if self._buffer_len - self._buffer_offset > self._buffer_size:
            if not self._start_response:
                self.__call_start_response()
            #endif
            self._buffer.seek(self._buffer_offset)
            self.__write(self._buffer.read(self._buffer_size))
            self._buffer_offset += self._buffer_size
            self._buffer.seek(0,2)  # seek to EOF
            self.body_bytes_sent = self._buffer_offset
        if flush == 1:
            self.flush()
    #enddef

    def __call_start_response(self):
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
        """ only set {REQUEST_URI} variable if not exist """
        if 'REQUEST_URI' not in self.environ:
            self.subprocess_env['REQUEST_URI'] = self.environ.get('PATH_INFO')

    def get_options(self):
        """ Returns dictionary with application variables from server
            environment. Application variables start with {app_} prefix,
            but in returned dictionary is set without this prefix.

                #!ini
                poor_LogLevel = warn       # Poor WSGI variable
                app_db_server = localhost   # application variable db_server
                app_templates = app/templ   # application variable templates
        """
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
        """
        An interface to log error via wsgi.errors.
            message - string with the error message
            level - is one of the following flags constants:
                        LOG_EMERG
                        LOG_ALERT
                        LOG_CRIT
                        LOG_ERR     (default)
                        LOG_WARNING
                        LOG_NOTICE
                        LOG_INFO
                        LOG_DEBUG
                        LOG_NOERRNO
            server - interface only compatibility parameter
        """

        if self._log_level[0] >= level[0]:
            self._errors.write("<%s> %s\n" % (level[1], message))

    def __reset_buffer__(self):
        """ Clean _buffer - for internal server error use. It could be used in
            error pages, typical in internal_server_error. But be careful,
            this method not help you, when any data was sent to wsgi server.
        """
        self._buffer = BytesIO()    # reset method not exist in python3.x
        #self._buffer.reset()
        #self._buffer.truncate()
        self._buffer_len = 0
        self._buffer_offset = 0
        self.body_bytes_sent = 0
    #enddef

    def __end_of_request__(self):
        """
        Method for internal use only!. This method was called from Application
        object at the end of request for returning right value to wsgi server.
        """
        if not self._start_response:
            self.set_content_lenght(self._buffer_len)
            self.__call_start_response()
            self._buffer_offset = self._buffer_len
            self._buffer.seek(0)    # na zacatek !!
            return self._buffer     # return buffer (StringIO or BytesIO)
        else:
            self._buffer.seek(self._buffer_offset)
            self.__write(self._buffer.read())   # flush all from buffer
            self._buffer_offset = self._buffer_len
            self.body_bytes_sent = self._buffer_len
            return ()               # data was be sent via write method
        #enddef
    #enddef

    def flush(self):
        """Flushes the output buffer."""
        if not self._start_response:
            self.__call_start_response()

        self._buffer.seek(self._buffer_offset)
        self.__write(self._buffer.read())       # flush all from buffer
        self._buffer_offset = self._buffer_len
        self.body_bytes_sent = self._buffer_len
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
        """ Sets Content-Length value for output header. This value was set
            automatically when size of output data are less then buffer size.
        """
        self.clength = length
    #enddef

#endclass

class EmptyForm(dict):
    """
    Compatibility class as fallback, for poor_AutoArgs or poor_AutoForm is set
    to Off.
    """
    def getvalue(self, name, default = None):
        return None

    def getfirst(self, name, default = None, fce = uni):
        return None

    def getlist(self, name, fce = uni):
        return []


class Args(dict):
    """
    Compatibility class for read values from QUERY_STRING based on dictionary.
    It has getfirst and getlist methods, which can call function on values.
    """
    def __init__(self, req, keep_blank_values=0, strict_parsing=0):
        qs = req.environ.get('QUERY_STRING', '').strip()
        args = parse_qs(qs, keep_blank_values, strict_parsing) if qs else {}
        dict.__init__(self, ((key, val[0] if len(val) < 2 else val) \
                                    for key, val in args.items() ))

    def getvalue(self, name, default = None):
        """ compatibility methods with FieldStorage, alias for get """
        return self.get(name, default)

    def getfirst(self, name, default = None, fce = uni):
        """
        Returns first variable value for key or default, if key not exist.
        fce - function which processed value, str is default.
        """
        val = self.get(name, default)
        if val is None: return None

        if isinstance(val, list):
            return fce(val[0])
        return fce(val)
    #enddef

    def getlist(self, name, fce = uni):
        """
        Returns list of variable values for key or empty list, if key not exist.
        fce - function which processed value, str is default.
        """
        val = self.get(name, None)
        if val is None: return []

        if isinstance(val, list):
            return map(fce, val)
        return [fce(val),]


class FieldStorage(CgiFieldStorage):
    """
    Class based of cgi.FieldStorage. Instead of FieldStorage from cgi module,
    can have better getfirst and getlist methods which can call function on
    values and can set file_callback.

    Constructor post special environment to base class, which do POST emulation
    for any request, because base cgi.FieldStorage know only GET, HEAD and POST
    methods an read from all variables, which we don't want.

    There are some usable variables, which you can use, if you want to test what
    variable it is:
        name - variable name, the same name from input attribute.
        type - content-type of variable. All variables have internal
              content-type, if that is no file, content-type is text/plain.
        filename - if variable is file, filename is its name from form.
        file - file type instance, from you can read variable. This instance
              could be TemporaryFile as default for files, StringIO for normal
              variables or instance of your own file type class, create from
              file_callback.
        lists - if variable is list of variables, this contains instances of
              FieldStorage.
    """
    def __init__(self, req, headers = None, outerboundary = b'', environ = {},
                 keep_blank_values = 0, strict_parsing = 0, limit = None,
                 encoding = 'utf-8', errors = 'replace', file_callback = None):
        """ Many of input parameters are need only for next internal use, because
            FieldStorage parse variables recursive. You need add only:
                req             - Request object.
                keep_blank_values - if you want to parse blank values as right
                                 empty values.
                strict_parsing  - if you want to raise exception on parsing
                                 error.
                file_callback   - callback for creating instance of uploading
                                 files.
        """

        if isinstance(req, Request):
            if req.environ.get('wsgi.input', None) is None:
                raise ValueError('No wsgi input File in request environment.')

            environ = {'REQUEST_METHOD': 'POST'}
            if 'CONTENT_TYPE' in req.environ:
                environ['CONTENT_TYPE'] = req.environ['CONTENT_TYPE']
            if 'CONTENT_LENGTH' in req.environ:
                environ['CONTENT_LENGTH'] = req.environ['CONTENT_LENGTH']
            if file_callback:
                environ['wsgi.file_callback'] = file_callback

            headers = req.headers_in
            req = req.environ.get('wsgi.input')

        self.environ = environ
        if version_info.major < 3:
            CgiFieldStorage.__init__( self, req, headers, outerboundary, environ,
                    keep_blank_values, strict_parsing)
        else:
            CgiFieldStorage.__init__( self, req, headers, outerboundary, environ,
                    keep_blank_values, strict_parsing, limit, encoding, errors)
    #enddef

    def make_file(self, binary = None):
        """ Return readable and writable temporary file.
                binary - unused. Here is only for backward compatibility
        """
        if 'wsgi.file_callback' in self.environ:
            return self.environ['wsgi.file_callback'](self.filename)
        else:
            return CgiFieldStorage.make_file(self)
    #enddef

    def get(self, key, default = None):
        """ compatibility methods with dict, alias for getvalue """
        return self.getvalue(key, default)

    def getfirst(self, name, default = None, fce = uni):
        """
        Returns first variable value for key or default, if key not exist.
        fce - function which processed value, str is default.
        """
        val = CgiFieldStorage.getfirst(self, name, default)
        if val is None: return None

        return fce(val)
    #enddef

    def getlist(self, name, fce = uni):
        """
        Returns list of variable values for key or empty list, if key not exist.
        fce - function which processed value, str is default.
        """
        val = CgiFieldStorage.getlist(self, name)
        return map(fce, val)
    #enddef

#endclass

class SERVER_RETURN(SERVER_RETURN_RIGHT):
    """Compatible with mod_python.apache exception."""
    def __init__(self, code = HTTP_INTERNAL_SERVER_ERROR):
        """deprecated location, use results.SERVER_RETURN"""

        stderr.write("[W] Using deprecated location of SERVER_RETURN in\n")
        for s in stack()[1:]:
            stderr.write("  File %s, line %s, in %s\n" % s[1:4])
            stderr.write(s[4][0])
        stderr.write("  Use results.SERVER_RETURN insead of")
        stderr.write(" requests.SERVER_RETURN.\n\n")
        stderr.flush()

        SERVER_RETURN_RIGHT.__init__(self, code)
#endclass
