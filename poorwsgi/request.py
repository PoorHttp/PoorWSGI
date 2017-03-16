"""
Headers, Request and FieldStorage classes, which is used for managing requests.
"""

from collections import Mapping
from wsgiref.headers import _formatparam
from cgi import FieldStorage as CgiFieldStorage, parse_header
from sys import version_info, stderr
from inspect import stack
from json import loads as json_loads
from io import BytesIO

import os
import re

if version_info[0] < 3:         # python 2.x
    from httplib import responses
    from urlparse import parse_qs
    from Cookie import SimpleCookie

else:                           # python 3.x
    from http.client import responses
    from urllib.parse import parse_qs
    from http.cookies import SimpleCookie

from poorwsgi.state import methods, levels, \
    LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG, METHOD_POST, METHOD_PUT, \
    METHOD_PATCH, HTTP_OK

from poorwsgi.results import _unicode_exist, uni

# simple regular expression for construct_url method
re_httpUrlPatern = re.compile(r"^(http|https):\/\/")


class Headers(Mapping):
    """Class inherited from collections.Mapping.

    As PEP 0333, resp. RFC 2616 says, all headers names must be only US-ASCII
    character except control characters or separators. And headers values must
    be store in string encoded in ISO-8859-1. This class methods Headers.add
    and Headers.add_header do auto convert values from UTF-8 to ISO-8859-1
    encoding if it is possible. So on every modification methods must be use
    UTF-8 string or unicode.
    """

    def __init__(self, headers=list(), strict=True):
        """Headers constructor.

        Headers object could be create from list, set or tuple of pairs
        name, value. Or from dictionary. All names or values must be
        iso-8859-1 encodable. If not, AssertionError will be raised.

        If strict is False, headers names and values are not encoded to
        iso-8859-1. This is for input headers using only!
        """
        if isinstance(headers, (list, tuple, set)):
            if strict:
                self.__headers = list(
                    (Headers.iso88591(k), Headers.iso88591(v))
                    for k, v in headers)
            else:
                self.__headers = list((k, v) for k, v in headers)
        elif isinstance(headers, dict):
            if strict:
                self.__headers = list(
                    (Headers.iso88591(k), Headers.iso88591(v))
                    for k, v in headers.items())
            else:
                self.__headers = list((k, v) for k, v in headers.items())
        else:
            raise AssertionError("headers must be tuple, list or set "
                                 "of str or unicode, or dict "
                                 "(got {0})".format(type(headers)))
    # enddef

    def __len__(self):
        """Return len of header items."""
        return len(self.__headers)

    def __getitem__(self, name):
        """Return header item identified by lower name."""
        name = Headers.iso88591(name.lower())
        for k, v in self.__headers:
            if k.lower() == name:
                return v
        raise KeyError("{0!r} is not registered".format(name))

    def __delitem__(self, name):
        """Delete item identied by lower name."""
        name = Headers.iso88591(name.lower())
        self.__headers = list(kv for kv in self.__headers
                              if kv[0].lower() != name)

    def __setitem__(self, name, value):
        """Delete item if exist and set it's new value."""
        del self[name]
        self.add_header(name, value)

    def __iter__(self):
        return iter(self.__headers)

    def __repr__(self):
        return "Headers(%r)" % repr(tuple(self.__headers))

    def names(self):
        """Return tuple of headers names."""
        return tuple(k for k, v in self.__headers)

    def keys(self):
        """Alias for names method."""
        return self.names()

    def values(self):
        """Return tuple of headers values."""
        return tuple(v for k, v in self.__headers)

    def get_all(self, name):
        """Return tuple of all values of header identifed by lower name."""
        name = Headers.iso88591(name.lower())
        return tuple(kv[1] for kv in self.__headers if kv[0].lower() == name)

    def items(self):
        """Return tuple of headers pairs."""
        return tuple(self.__headers)

    def setdefault(self, name, value):
        """Set header value if not exist, and return it's value."""
        res = self.get(name)
        if res is None:
            self.add_header(name, value)
            return value
        else:
            return res

    def add(self, name, value):
        """Set header name to value.

        Duplicate names are not allowed instead of {Set-Cookie}.
        """
        if name != "Set-Cookie" and name in self:
            raise KeyError("Key %s exist." % name)
        self.add_header(name, value)

    def add_header(self, name, value, **kwargs):
        """Extended header setting.

        name is the header field to add. kwargs arguments can be used to set
        additional parameters for the header field, with underscores converted
        to dashes.  Normally the parameter will be added as name="value" unless
        value is None, in which case only the name will be added.

            h.add_header('Content-Disposition', 'attachment',
                         filename='image.png')

        All names must be US-ASCII string except control characters
        or separators.
        """

        parts = []

        if value is not None:
            parts.append(Headers.iso88591(value))

        for k, v in kwargs.items():
            k = Headers.iso88591(k)
            if v is None:
                parts.append(k.replace('_', '-'))
            else:
                parts.append(_formatparam(k.replace('_', '-'),
                             Headers.iso88591(v)))
        self.__headers.append((Headers.iso88591(name), "; ".join(parts)))

    @staticmethod
    def iso88591(value):
        """Doing automatic conversion to iso-8859-1 strings.

        In python 2.x can convert unicode to iso-8859-1 strings, or from utf-8
        string to iso-8859-1 string. On python 3.x converts from utf-8 to
        iso-8859-1 string. That means, all input value of Headers class
        must be UTF-8 stings.
        """
        try:
            if not _unicode_exist and isinstance(value, str):
                return value.encode('utf-8').decode('iso-8859-1')
            if _unicode_exist and isinstance(value, str):
                return value.decode('utf-8').encode('iso-8859-1')
            if _unicode_exist and isinstance(value, unicode):
                return value.encode('iso-8859-1')

        except UnicodeError:
                raise AssertionError("Header name/value must be iso-8859-1 "
                                     "encoded (got {0})".format(value))
        if not _unicode_exist:
            raise AssertionError("Header name/value must be of type str "
                                 "(got {0})".format(value))
        else:
            raise AssertionError("Header name/value must be of type str or "
                                 "unicode (got {0})".format(value))
# endclass Headers


class Request(object):
    """HTTP request object with all server elements.

    It could be compatible as soon as possible with mod_python.apache.request.

    Special variables for user use:
        app_            - as prefix for any your application variable (not
                          defined)

    """

    def __init__(self, environ, start_response, app_config):
        """Object was created automatically in wsgi module.

        It's input parameters are the same, which Application object gets from
        WSGI server plus file callback for auto request body parsing.
        """
        self.__app_config = app_config
        self.__environ = environ
        if 'REQUEST_URI' not in environ:
            self.__environ['REQUEST_URI'] = environ.get('PATH_INFO')

        # The path portion of the URI.
        self.__uri_rule = None

        # Reference to final uri_handler, user can use some handler attributes
        self.__uri_handler = None

        # String. The content type. Another way to set content_type is via
        # headers_out object property. Default is text/html; charset=utf-8
        self.__content_type = "text/html; charset=utf-8"

        self.__clength = 0

        self.__body_bytes_sent = 0

        # Status. One of http.enums.HTTP_* values.
        self.__status = HTTP_OK

        # A table object containing headers sent by the client.
        tmp = []
        for key, val in self.__environ.items():
            if key[:5] == 'HTTP_':
                key = '-'.join(map(lambda x: x.capitalize(),
                                   key[5:].split('_')))
                tmp.append((key, val))
            elif key in ("CONTENT_LENGTH", "CONTENT_TYPE"):
                key = '-'.join(map(lambda x: x.capitalize(),
                                   key.split('_')))
                tmp.append((key, val))

        self.__headers_in = Headers(tmp, False)  # do not convert to iso-8859-1

        # A Headers object representing the headers to be sent to the client.
        self.__headers_out = Headers(
            (("X-Powered-By", "Poor WSGI for Python"),))

        # These headers get send with the error response, instead of
        # headers_out.
        self.__err_headers_out = Headers(
            (("X-Powered-By", "Poor WSGI for Python"),))

        # uwsgi do not sent environ variables to apps environ
        if 'uwsgi.version' in self.__environ or 'poor.Version' in os.environ:
            self.__poor_environ = os.environ
        else:
            self.__poor_environ = self.__environ

        self._file = self.__environ.get("wsgi.input")
        self._errors = self.__environ.get("wsgi.errors")

        # args
        if app_config['auto_args']:
            self.__args = Args(self, app_config['keep_blank_values'],
                               app_config['strict_parsing'])
        else:
            self.__args = EmptyForm()

        ctype, pdict = parse_header(self.__headers_in.get('content-type', ''))
        # test auto json parsing
        if app_config['auto_json'] and self.is_body_request \
                and ctype in app_config['json_content_types']:
            self.__json = Json(self, pdict.get('charset', 'utf-8'))
            self.__form = EmptyForm()
        # test auto form parsing
        elif app_config['auto_form'] and self.is_body_request \
                and ctype in app_config['form_content_types']:
            self.__form = FieldStorage(
                self, keep_blank_values=app_config['keep_blank_values'],
                strict_parsing=app_config['strict_parsing'])
            self.__json = EmptyForm()
        else:
            self.__form = EmptyForm()
            self.__json = EmptyForm()

        if app_config['auto_cookies'] and 'Cookie' in self.__headers_in:
            self.__cookies = SimpleCookie()
            self.__cookies.load(self.__headers_in['Cookie'])
        else:
            self.__cookies = tuple()

        self.__debug = self.__poor_environ.get(
            'poor_Debug', app_config['debug']).lower() == 'on'

        self.start_response = start_response
        self._start_response = False

        self._buffer = BytesIO()
        self._buffer_len = 0
        self._buffer_offset = 0

        try:
            self._log_level = levels[self.__poor_environ.get(
                'poor_LogLevel', 'warn').lower()]
        except:
            self._log_level = LOG_WARNING
            self.log_error('Bad poor_LogLevel, default is warn.', LOG_WARNING)

        try:
            self._buffer_size = int(self.__poor_environ.get('poor_BufferSize',
                                                            '16384'))
        except:
            self._buffer_size = 16384
            self.log_error('Bad poor_BufferSize, default is 16384 B (16 KiB).',
                           LOG_WARNING)

        # variables for user use
        self.__config = None
        self.__user = None
    # enddef

    # -------------------------- Properties --------------------------- #
    @property
    def environ(self):
        """Copy of table object containing request environment.

        Information is get from wsgi server.
        """
        return self.__environ.copy()

    @property
    def hostname(self):
        """Host, as set by full URI or Host: header."""
        return self.__environ.get('HTTP_HOST')

    @property
    def method(self):
        """String containing the method - {GET}, {HEAD}, {POST}, etc."""
        return self.__environ.get('REQUEST_METHOD')

    @property
    def method_number(self):
        """Method number constant from state module."""
        if self.method not in methods:
            return methods['GET']
        return methods[self.method]

    @property
    def uri(self):
        """The path portion of the URI."""
        return uni(self.__environ.get('PATH_INFO'))

    @property
    def uri_rule(self):
        """Rule from one of application handler table.

        This property could be set once, and that do Application object. There
        are some internal uri_rules which is set typical if some internal
        handler was called. There are: {_default_handler_, _directory_index_,
        _debug_info_ and _send_file_ }. In other case, there be url or regex.
        """
        return self.__uri_rule

    @uri_rule.setter
    def uri_rule(self, value):
        if self.__uri_rule is None:
            self.__uri_rule = value

    @property
    def uri_handler(self):
        """This property is set at the same point as uri_rule.

        It was set by Application object when end point handler is known before
        calling all pre handlers. Typical use case is set some special
        attribute to handler, and read them in pre handler.
        """
        return self.__uri_handler

    @uri_handler.setter
    def uri_handler(self, value):
        if self.__uri_handler is None:
            self.__uri_handler = value

    @property
    def content_type(self):
        """Content-Type header string, by default {text/html; charset=utf-8}.

        Another way to set content_type is via headers_out object property.
        """
        return self.__content_type

    @content_type.setter
    def content_type(self, value):
        self.__content_type = value

    @property
    def clength(self):
        """Property to store output content length for header.

        This value was set automatically when size of output data are less then
        buffer size.
        """
        return self.__clength

    @clength.setter
    def clength(self, value):
        self.__clength = value

    @property
    def body_bytes_sent(self):
        """Internal variable to store count of bytes which are really sent."""
        return self.__body_bytes_sent

    @property
    def status(self):
        """Http status code, which is *state.HTTP_OK (200)* by default.

        If you want to set this variable (which is very good idea in http_state
        handlers), it is good solution to use some of HTTP_ constant from
        state module.
        """
        return self.__status

    @status.setter
    def status(self, value):
        if value not in responses:
            raise ValueError("Bad response status %s" % value)
        self.__status = value

    @property
    def headers_in(self):
        """Reference to input headers object."""
        return self.__headers_in

    @property
    def is_xhr(self):
        """.If X-Requested-With header is set and have XMLHttpRequest value."""
        return self.__headers_in.get('X-Requested-With') == 'XMLHttpRequest'

    @property
    def is_body_request(self):
        """True if request is body request type, so it is PATCH, POST or PUT.
        """
        return self.method_number & (METHOD_PATCH | METHOD_POST | METHOD_PUT)

    @property
    def headers_out(self):
        """Reference to output headers object."""
        return self.__headers_out

    @headers_out.setter
    def headers_out(self, value):
        if not isinstance(value, Headers):
            raise ValueError("Headers must be instance of "
                             "wsgiref.headers.Headers")
        self.__headers_out = value

    @property
    def err_headers_out(self):
        """Reference to output headers object for error pages."""
        return self.__err_headers_out

    @property
    def poor_environ(self):
        """Environ with poor_ variables.

        It is environ from request, or os.environ
        """
        return self.__poor_environ.copy()

    @property
    def args(self):
        """Extended dictionary (Args instance) of request arguments.

        Argument are parsed from QUERY_STRING, which is typical, but not only
        for GET method. Arguments are parsed when Application.auto_args is set
        which is default.

        This property could be *set only once*.
        """
        return self.__args

    @args.setter
    def args(self, value):
        if isinstance(self.__args, EmptyForm):
            self.__args = value

    @property
    def form(self):
        """Dictionary like class (FieldStorage instance) of body arguments.

        Arguments must be send in request body with content type
        one of Application.form_content_types. Method must be POST, PUT
        or PATCH. Request body is parsed when Application.auto_form
        is set, which default and when method is POST, PUT or PATCH.

        This property could be *set only once*.
        """
        return self.__form

    @form.setter
    def form(self, value):
        if isinstance(self.__form, EmptyForm):
            self.__form = value

    @property
    def json(self):
        """Json dictionary if request content type is JSON.

        Json types is defined in Application.json_content_types, typical is
        {application/json} and request method must be POST, PUT or PATCH and
        Application.auto_json must be set to true (default). Otherwise json
        is EmptyForm.
        """
        return self.__json

    @property
    def cookies(self):
        """SimpleCookie iterable object of all cookies from Cookie header.

        This property was set if Application.auto_cookies is set to true,
        which is default. Otherwise cookies was empty tuple.
        """
        return self.__cookies

    @property
    def debug(self):
        """Value of poor_Debug variable."""
        return self.__debug

    @property
    def remote_host(self):
        """Remote hostname."""
        return self.__environ.get('REMOTE_HOST', '')

    @property
    def remote_addr(self):
        """Remote address."""
        return self.__environ.get('REMOTE_ADDR')

    @property
    def referer(self):
        """Request referer if is available or None."""
        return self.__environ.get('HTTP_REFERER')

    @property
    def user_agent(self):
        """Browser user agent string."""
        return self.__environ.get('HTTP_USER_AGENT')

    @property
    def server_scheme(self):
        """Request scheme, typical {http} or {https}."""
        return self.__environ.get('wsgi.url_scheme')

    @property
    def scheme(self):
        """Alias for server_scheme property."""
        return self.__environ.get('wsgi.url_scheme')

    @property
    def server_software(self):
        """Server software."""
        ss = self.__environ.get('SERVER_SOFTWARE', 'Unknown')
        if ss == 'Unknown' and 'uwsgi.version' in self.__environ:
            ss = 'uWsgi'
        return ss

    @property
    def server_admin(self):
        """Server admin if set, or webmaster@hostname."""
        return self.__environ.get('SERVER_ADMIN',
                                  'webmaster@%s' % self.hostname)

    @property
    def server_hostname(self):
        """Server name variable."""
        return self.__environ.get('SERVER_NAME')

    @property
    def server_port(self):
        """Server port."""
        return int(self.__environ.get('SERVER_PORT'))

    @property
    def port(self):
        """Alias for server_port property."""
        return int(self.__environ.get('SERVER_PORT'))

    @property
    def server_protocol(self):
        """Server protocol, as given by the client.

        In HTTP/0.9. cgi SERVER_PROTOCOL value.
        """
        return self.__environ.get('SERVER_PROTOCOL')

    @property
    def protocol(self):
        """Alias for server_protocol property"""
        return self.__environ.get('SERVER_PROTOCOL')

    @property
    def forwarded_for(self):
        """X-Forward-For http header if exists."""
        return self.__environ.get('HTTP_X_FORWARDED_FOR')

    @property
    def forwarded_host(self):
        """X-Forward-Host http header if exists."""
        return self.__environ.get('HTTP_X_FORWARDED_HOST')

    @property
    def forwarded_proto(self):
        """X-Forward-Proto http header if exists."""
        return self.__environ.get('HTTP_X_FORWARDED_PROTO')

    @property
    def secret_key(self):
        """Value of poor_SecretKey variable.

        Secret key is used by PoorSession class. It is generate from
        some server variables, and the best way is set programmatically
        by Application.secret_key from random data.
        """
        return self.__poor_environ.get(
            'poor_SecretKey',
            self.__app_config['secret_key'])

    @property
    def secretkey(self):
        """*DEPRECATED* alias for secret_key."""
        stderr.write("[W] Using deprecated property secretkey in\n")
        for s in stack()[1:]:
            stderr.write("  File %s, line %s, in %s\n" % s[1:4])
            stderr.write(s[4][0])
            stderr.flush()

        return self.secret_key

    @property
    def document_index(self):
        """Value of poor_DocumentIndex variable.

        Variable is used to generate index html page, when poor_DocumentRoot
        is set.
        """
        return self.__poor_environ.get(
            'poor_DocumentIndex',
            self.__app_config['document_index']).lower() == 'on'

    @property
    def config(self):
        """For config object (default None)."""
        return self.__config

    @config.setter
    def config(self, value):
        self.__config = value

    @property
    def logger(self):
        """*DEPRECATED* For special logger function (default req.log_error).

        Use log_error, log_info, log_debug or logging method instead of that.
        """
        stderr.write("[W] Using deprecated logger attribute\n")
        for s in stack()[1:]:
            stderr.write("  File %s, line %s, in %s\n" % s[1:4])
            stderr.write(s[4][0])
        stderr.flush()

        return self.log_error

    @property
    def user(self):
        """For user object, who is login for example (default None)."""
        return self.__user

    @user.setter
    def user(self, value):
        self.__user = value

    # -------------------------- Methods --------------------------- #
    def __read(self, length=-1):
        return self._file.read(length)

    def read(self, length=-1):
        """Read data from client (typical for XHR2 data POST).

        If length is not set, or if is lower then zero, Content-Length was
        be use.
        """
        content_length = int(self.__headers_in.get("Content-Length", 0))
        if content_length == 0:
            self.log_error("No Content-Length found, read was failed!",
                           LOG_ERR)
            return ''
        if length > -1 and length < content_length:
            self.read = self.__read
            return self.read(length)
        return self._file.read(content_length)
    # enddef

    def write(self, data, flush=0):
        """Write data to buffer.

        If len of data is bigger then poor_BufferSize, data was be sent
        to client via old write method (directly). Otherwise, data was be sent
        at the end of request as iterable object.
        """
        if (not _unicode_exist and isinstance(data, str)) \
                or (_unicode_exist and isinstance(data, unicode)):
            data = data.encode('utf-8')

        # FIXME: self._buffer is not FIFO
        self._buffer_len += len(data)
        self._buffer.write(data)
        if self._buffer_len - self._buffer_offset > self._buffer_size:
            if not self._start_response:
                self.__call_start_response()
            # endif
            self._buffer.seek(self._buffer_offset)
            try:
                self.__write(self._buffer.read(self._buffer_size))
            except Exception:
                raise BrokenClientConnection(self.remote_host,
                                             self.remote_addr)
            self._buffer_offset += self._buffer_size
            self._buffer.seek(0, 2)  # seek to EOF
            self.__body_bytes_sent = self._buffer_offset
        if flush == 1:
            self.flush()
    # enddef

    def __call_start_response(self):
        if self.__status == 304:
            # Not Modified MUST NOT include other entity-headers
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
            if 'Content-Encoding' in self.__headers_out \
                    or 'Content-Language' in self.__headers_out \
                    or 'Content-Length' in self.__headers_out \
                    or 'Content-Location' in self.__headers_out \
                    or 'Content-MD5' in self.__headers_out \
                    or 'Content-Range' in self.__headers_out \
                    or 'Content-Type' in self.__headers_out:
                self.log_error('Some entity header in Not Modified response',
                               LOG_WARNING)
            if 'Date' not in self.__headers_out:
                self.log_error('Missing Date header in Not Modified response',
                               LOG_WARNING)
        else:
            if self.__content_type \
                    and not self.__headers_out.get('Content-Type'):
                self.__headers_out.add('Content-Type', self.__content_type)
            elif not self.__content_type \
                    and not self.__headers_out.get('Content-Type'):
                self.log_error('Content-type not set!', LOG_WARNING)

            if self.__clength and not self.__headers_out.get('Content-Length'):
                self.__headers_out.add('Content-Length', str(self.__clength))
        # endif

        self.__write = self.start_response(
            "%d %s" % (self.__status, responses[self.__status]),
            list(self.__headers_out.items()))
        self._start_response = True
    # enddef

    def get_options(self):
        """Returns dictionary with application variables from environment.

        Application variables start with {app_} prefix, but in returned
        dictionary is set without this prefix.

                #!ini
                poor_LogLevel = warn        # Poor WSGI variable
                app_db_server = localhost   # application variable db_server
                app_templates = app/templ   # application variable templates
        """
        options = {}
        for key, val in self.__poor_environ.items():
            key = key.strip()
            if key[:4].lower() == 'app_':
                options[key[4:].lower()] = val.strip()
        return options

    def get_remote_host(self):
        """Returns REMOTE_ADDR CGI enviroment variable."""
        return self.remote_addr

    def document_root(self):
        """Returns DocumentRoot setting."""
        document_root = self.__poor_environ.get(
            'poor_DocumentRoot',
            self.__app_config['document_root'])
        self.log_error("poor_DocumentRoot: %s" % document_root,
                       LOG_INFO)
        return document_root

    def construct_url(self, uri):
        """This function returns a fully qualified URI string.

        Url is create from the path specified by uri, using the information
        stored in the request to determine the scheme, server host name
        and port. The port number is not included in the string if it is the
        same as the default port 80."""

        if not re_httpUrlPatern.match(uri):
            return "%s://%s%s" % (self.forwarded_proto or self.server_scheme,
                                  self.forwarded_host or self.hostname, uri)
        return uri
    # enddef

    def log_error(self, message, level=LOG_ERR, server=None):
        """An interface to log error via wsgi.errors.

        Arguments:
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
            if _unicode_exist and isinstance(message, unicode):
                message = message.encode('utf-8')
            try:
                self._errors.write("<%s> %s\n" % (level[1], message))
            except UnicodeEncodeError:
                if _unicode_exist:
                    message = message.decode('utf-8').encode(
                        'ascii', 'backslashreplace')
                else:
                    message = message.encode(
                        'ascii', 'backslashreplace').decode('ascii')
                self._errors.write("<%s> %s\n" % (level[1], message))
            self._errors.flush()

    def log_info(self, message):
        """Logging method, which create message as LOG_INFO level."""
        self.log_error(message, LOG_INFO)

    def log_debug(self, message):
        """Logging method, which create message as LOG_DEBUG level."""
        self.log_error(message, LOG_DEBUG)

    def log_warning(self, message):
        """Logging method, which create message as LOG_WARNING level."""
        self.log_error(message, LOG_WARNING)

    def __reset_buffer__(self):
        """Clean _buffer (*for internal server error use*).

        It could be used in error pages, typical in internal_server_error.
        But be careful, this method not help you, when any data was sent
        to wsgi server.
        """
        self._buffer = BytesIO()    # reset method not exist in python3.x
        # self._buffer.reset()
        # self._buffer.truncate()
        self._buffer_len = 0
        self._buffer_offset = 0
        self.__body_bytes_sent = 0
    # enddef

    def __end_of_request__(self):
        """Method *for internal use only!*.

        This method was called from Application object at the end of request
        for returning right value to wsgi server.
        """
        if not self._start_response:
            self.__clength = self._buffer_len
            self.__call_start_response()
            self._buffer_offset = self._buffer_len
            self._buffer.seek(0)    # na zacatek !!
            return self._buffer     # return buffer (BytesIO)
        else:
            self._buffer.seek(self._buffer_offset)
            try:
                self.__write(self._buffer.read())   # flush all from buffer
            except Exception:
                raise BrokenClientConnection(self.remote_host,
                                             self.remote_addr)
            finally:
                self._buffer.close()
            self._buffer_offset = self._buffer_len
            self.__body_bytes_sent = self._buffer_len
            return ()               # data was be sent via write method
        # enddef
    # enddef

    def __del__(self):
        self.log_debug("Request: Hasta la vista, baby.")

    def flush(self):
        """Flushes the output buffer."""
        if not self._start_response:
            self.__call_start_response()

        self._buffer.seek(self._buffer_offset)
        try:
            self.__write(self._buffer.read())       # flush all from buffer
        except Exception:
            raise BrokenClientConnection(self.remote_host, self.remote_addr)
        self._buffer_offset = self._buffer_len
        self.__body_bytes_sent = self._buffer_len
    # enddef

    def sendfile(self, path, offset=0, limit=-1):
        """Send file defined by path to client.

        Offset and len is not supported yet.

            @app.route('myfile.txt')
            def myfile(req):
                req.content_type('text/plain')
                length = req.sendfile('myfile.txt')
                req.log_error('sending myfile.txt with %d length' % length)
        """
        if not os.access(path, os.R_OK):
            raise IOError("Could not stat file for reading")

        length = 0
        with open(path, 'r') as bf:
            data = bf.read(self._buffer_size)
            while data:
                length += len(data)
                self.write(data)
                data = bf.read(self._buffer_size)

        return length
    # enddef

    def set_content_lenght(self, length):
        """*DEPRECATED* Use req.clength = length instead of call this method.
        """
        self.clength = length

        stderr.write("[W] Using deprecated method set_content_lenght in\n")
        for s in stack()[1:]:
            stderr.write("  File %s, line %s, in %s\n" % s[1:4])
            stderr.write(s[4][0])
        stderr.flush()
    # enddef

# endclass


class EmptyForm(dict):
    """Compatibility class as fallback.

    This class is used when poor_AutoArgs or poor_AutoForm is set to Off.
    """
    def getvalue(self, name, default=None):
        return default

    def getfirst(self, name, default=None, fce=uni):
        return fce(default) if default is not None else default

    def getlist(self, name, fce=uni):
        return []


class Args(dict):
    """Compatibility class for read values from QUERY_STRING.

    Class is based on dictionary. It has getfirst and getlist methods,
    which can call function on values.
    """
    def __init__(self, req, keep_blank_values=0, strict_parsing=0):
        qs = req.environ.get('QUERY_STRING', '').strip()
        args = parse_qs(qs, keep_blank_values, strict_parsing) if qs else {}
        dict.__init__(self, ((key, val[0] if len(val) < 2 else val)
                             for key, val in args.items()))

        self.getvalue = self.get

    def getfirst(self, name, default=None, fce=uni):
        """Returns first variable value for key or default.

        Arguments:
            fce - function which processed value.
        """
        val = self.get(name, default)
        if val is None:
            return None

        if isinstance(val, list):
            return fce(val[0])
        return fce(val)
    # enddef

    def getlist(self, name, fce=uni):
        """Returns list of variable values for key or empty list.

        Arguments:
            fce - function which processed value.
        """
        val = self.get(name, None)
        if val is None:
            return []

        if isinstance(val, list):
            return map(fce, val)
        return [fce(val)]


class Json(dict):
    """Compatibility class for read values from JSON POST, PUT or PATCH request.

    It has getfirst and getlist methods, which can call function on values.
    """
    def __init__(self, req, charset):
        dict.__init__(self, json_loads(req.read().decode(charset)).items())
        self.getvalue = self.get

    def getfirst(self, name, default=None, fce=uni):
        """Returns first variable value for key or default, if key not exist.

        Arguments:
            fce - function which processed value.
        """
        val = self.get(name, default)
        if val is None:
            return None

        if isinstance(val, list):
            return fce(val[0])
        return fce(val)
    # enddef

    def getlist(self, name, fce=uni):
        """Returns list of variable values for key or empty list.

        Arguments:
            fce - function which processed value.
        """
        val = self.get(name, None)
        if val is None:
            return []

        if isinstance(val, list):
            return map(fce, val)
        return [fce(val)]


class FieldStorage(CgiFieldStorage):
    """Class based of cgi.FieldStorage.

    Instead of FieldStorage from cgi module, can have better getfirst
    and getlist methods which can call function on values and can set
    file_callback.

    Constructor post special environment to base class, which do POST emulation
    for any request, because base cgi.FieldStorage know only GET, HEAD and POST
    methods an read from all variables, which we don't want.

    There are some usable variables, which you can use, if you want to test
    what variable it is:
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
    def __init__(self, req, headers=None, outerboundary=b'', environ={},
                 keep_blank_values=0, strict_parsing=0, limit=None,
                 encoding='utf-8', errors='replace', file_callback=None):
        """Constructor of FieldStorage.

        Many of input parameters are need only for next internal use, because
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
        if version_info[0] < 3:
            CgiFieldStorage.__init__(self, req, headers, outerboundary,
                                     environ, keep_blank_values,
                                     strict_parsing)
        else:
            CgiFieldStorage.__init__(self, req, headers, outerboundary,
                                     environ, keep_blank_values,
                                     strict_parsing, limit, encoding, errors)
    # enddef

    def make_file(self, binary=None):
        """Return readable and writable temporary file.

        Arguments:
            binary - unused. Here is only for backward compatibility
        """
        if 'wsgi.file_callback' in self.environ:
            return self.environ['wsgi.file_callback'](self.filename)
        else:
            return CgiFieldStorage.make_file(self)
    # enddef

    def get(self, key, default=None):
        """Compatibility methods with dict, alias for getvalue."""
        return self.getvalue(key, default)

    def getfirst(self, name, default=None, fce=uni):
        """Returns first variable value for key or default, if key not exist.

        Arguments:
            fce - function which processed value.
        """
        val = CgiFieldStorage.getfirst(self, name, default)
        if val is None:
            return None

        return fce(val)
    # enddef

    def getlist(self, name, fce=uni):
        """Returns list of variable values for key or empty list.

        Arguments:
            fce - function which processed value, str is default.
        """
        val = CgiFieldStorage.getlist(self, name)
        return map(fce, val)
    # enddef
# endclass


class BrokenClientConnection(Exception):
    """Helping class for Broken Connection Pipe detect."""
    def __init__(self, remote_host, remote_addr):
        Exception.__init__(self, remote_host, remote_addr)

    def __str__(self):
        return "Broken client connection %s[%s]" % self.args
