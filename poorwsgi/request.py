"""Classes, which is used for managing requests.

:Classes:   Headers, Request, EmptyForm, Args, Json, FieldStorage
:Functions: parse_negotiation
"""

from collections.abc import Mapping
from wsgiref.headers import _formatparam
from cgi import FieldStorage as CgiFieldStorage, parse_header
from json import loads as json_loads
from io import BytesIO

import os
import re
from logging import getLogger

from urllib.parse import parse_qs
from http.cookies import SimpleCookie

from poorwsgi.state import methods, \
    METHOD_POST, METHOD_PUT, METHOD_PATCH

log = getLogger("poorwsgi")

# simple regular expression for construct_url method
re_httpUrlPatern = re.compile(r"^(http|https):\/\/")


def parse_negotiation(value):
    """Parse Content Negotiation headers to list of value, quality tuples."""
    values = []
    for it in value.split(','):
        pair = it.split(';')
        if pair[0] == it:
            values.append((it, 1.0))
            continue
        try:
            quality = float(pair[1].split('=')[1])
        except (IndexError, ValueError):
            quality = 1.0
        values.append((pair[0], quality))
    return values


class Headers(Mapping):
    """Class inherited from collections.Mapping.

    As PEP 0333, resp. RFC 2616 says, all headers names must be only US-ASCII
    character except control characters or separators. And headers values must
    be store in string encoded in ISO-8859-1. This class methods Headers.add
    and Headers.add_header do auto convert values from UTF-8 to ISO-8859-1
    encoding if it is possible. So on every modification methods must be use
    UTF-8 string.
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
                                 "of str, or dict "
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

        Duplicate names are not allowed instead of ``Set-Cookie``.
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

        .. code:: python

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

        Converts from utf-8 to iso-8859-1 string. That means, all input value
        of Headers class must be UTF-8 stings.
        """
        try:
            if isinstance(value, str):
                return value.encode('utf-8').decode('iso-8859-1')

        except UnicodeError:
            raise AssertionError("Header name/value must be iso-8859-1 "
                                 "encoded (got {0})".format(value))
        raise AssertionError("Header name/value must be of type str "
                             "(got {0})".format(value))
# endclass Headers


class Request(object):
    """HTTP request object with all server elements.

    It could be compatible as soon as possible with mod_python.apache.request.
    Special variables for user use are prefixed with ``app_``.
    """

    def __init__(self, environ, app_config):
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

        # Reference to final uri_handler, user can use some uri_handler
        # attributes
        self.__uri_handler = None

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

        self.__headers = Headers(tmp, False)  # do not convert to iso-8859-1

        ctype, pdict = parse_header(self.__headers.get('Content-Type', ''))
        self.__mime_type = ctype
        self.__charset = pdict.get('charset', 'utf-8')

        self.__content_length = int(self.__headers.get("Content-Length") or -1)
        # will be set with first property call
        self.__accept = None
        self.__accept_charset = None
        self.__accept_encoding = None
        self.__accept_language = None

        # uwsgi do not sent environ variables to apps environ
        if 'uwsgi.version' in self.__environ or 'poor.Version' in os.environ:
            self.__poor_environ = os.environ
        else:
            self.__poor_environ = self.__environ

        self.__file = self.__environ.get("wsgi.input")
        self._errors = self.__environ.get("wsgi.errors")
        self.__data = None

        if app_config['auto_data'] and \
                0 <= self.__content_length <= app_config['data_size']:
            self.__file = BytesIO(self.__file.read(self.__content_length))
            self.__file.seek(0)

        # path args are set via wsgi.handler_from_table
        self.__path_args = None

        # args
        if app_config['auto_args']:
            self.__args = Args(self, app_config['keep_blank_values'],
                               app_config['strict_parsing'])
        else:
            self.__args = EmptyForm()

        # test auto json parsing
        if app_config['auto_json'] and self.is_body_request \
                and self.__mime_type in app_config['json_mime_types']:
            self.__json = Json(self, self.__charset)
            self.__form = EmptyForm()
        # test auto form parsing
        elif app_config['auto_form'] and self.is_body_request \
                and self.__mime_type in app_config['form_mime_types']:
            self.__form = FieldStorage(
                self, keep_blank_values=app_config['keep_blank_values'],
                strict_parsing=app_config['strict_parsing'],
                file_callback=app_config['file_callback'])
            self.__json = EmptyForm()
        else:
            self.__form = EmptyForm()
            self.__json = EmptyForm()

        if app_config['auto_cookies'] and 'Cookie' in self.__headers:
            self.__cookies = SimpleCookie()
            self.__cookies.load(self.__headers['Cookie'])
        else:
            self.__cookies = tuple()

        self.__debug = self.__poor_environ.get(
            'poor_Debug', app_config['debug']).lower() == 'on'

        # variables for user use
        self.__config = None
        self.__user = None
    # enddef

    # -------------------------- Properties --------------------------- #
    @property
    def mime_type(self):
        """Request ``Content-Type`` header string."""
        return self.__mime_type

    @property
    def charset(self):
        """Request ``Content-Type`` charset header string, utf-8 if not set."""
        return self.__charset

    @property
    def content_length(self):
        """Request ``Content-Length`` header value, -1 if not set."""
        return self.__content_length

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
        """String containing the method, ``GET, HEAD, POST``, etc."""
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
        return self.__environ.get('PATH_INFO')

    @property
    def uri_rule(self):
        """Rule from one of application handler table.

        This property could be set once, and that do Application object. There
        are some internal uri_rules which is set typical if some internal
        handler was called. There are: ``/*`` for default, directory and file
        handler and ``/debug-info`` for debug handler. In other case, there be
        url or regex.
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

        Property was set when any route is found for request uri. Sending file
        internaly when document_root is set, or by Error handlers leave
        uri_handler None.
        """
        return self.__uri_handler

    @uri_handler.setter
    def uri_handler(self, value):
        if self.__uri_handler is None:
            self.__uri_handler = value

    @property
    def headers(self):
        """Reference to input headers object."""
        return self.__headers

    @property
    def accept(self):
        """Tuple of client supported mime types from Accept header."""
        if self.__accept is None:
            self.__accept = tuple(parse_negotiation(
                self.__headers.get("Accept", '')))
        return self.__accept

    @property
    def accept_charset(self):
        """Tuple of client supported charset from Accept-Charset header."""
        if self.__accept_charset is None:
            self.__accept_charset = tuple(parse_negotiation(
                self.__headers.get("Accept-Charset", '')))
        return self.__accept_charset

    @property
    def accept_encoding(self):
        """Tuple of client supported charset from Accept-Encoding header."""
        if self.__accept_encoding is None:
            self.__accept_encoding = tuple(parse_negotiation(
                self.__headers.get("Accept-Encoding", '')))
        return self.__accept_encoding

    @property
    def accept_language(self):
        """List of client supported languages from Accept-Language header."""
        if self.__accept_language is None:
            self.__accept_language = tuple(parse_negotiation(
                self.__headers.get("Accept-Language", '')))
        return self.__accept_language

    @property
    def accept_html(self):
        """Return true if ``text/html`` mime type is in accept neogetions
           values.
        """
        return "text/html" in dict(self.accept)

    @property
    def accept_xhtml(self):
        """Return true if ``text/xhtml`` mime type is in accept neogetions
           values.
        """
        return "text/xhtml" in dict(self.accept)

    @property
    def accept_json(self):
        """Return true if ``application/json`` mime type is in accept neogetions
           values.
        """
        return "application/json" in dict(self.accept)

    @property
    def is_xhr(self):
        """If ``X-Requested-With`` header is set with ``XMLHttpRequest`` value.
        """
        return self.__headers.get('X-Requested-With') == 'XMLHttpRequest'

    @property
    def is_body_request(self):
        """True if request is body request type, so it is PATCH, POST or PUT.
        """
        return self.method_number & (METHOD_PATCH | METHOD_POST | METHOD_PUT)

    @property
    def poor_environ(self):
        """Environ with ``poor_`` variables.

        It is environ from request, or os.environ
        """
        return self.__poor_environ.copy()

    @property
    def path_args(self):
        """Dictionary arguments from path of regual expression rule."""
        return (self.__path_args or {}).copy()

    @path_args.setter
    def path_args(self, value):
        if self.__path_args is None:
            self.__path_args = value

    @property
    def args(self):
        """Extended dictionary (Args instance) of request arguments.

        Argument are parsed from QUERY_STRING, which is typical, but not only
        for GET method. Arguments are parsed when Application.auto_args is set
        which is default.

        This property could be **set only once**.
        """
        return self.__args

    @args.setter
    def args(self, value):
        if isinstance(self.__args, EmptyForm):
            self.__args = value

    @property
    def form(self):
        """Dictionary like class (FieldStorage instance) of body arguments.

        Arguments must be send in request body with mime type
        one of Application.form_mime_types. Method must be POST, PUT
        or PATCH. Request body is parsed when Application.auto_form
        is set, which default and when method is POST, PUT or PATCH.

        This property could be **set only once**.
        """
        return self.__form

    @form.setter
    def form(self, value):
        if isinstance(self.__form, EmptyForm):
            self.__form = value

    @property
    def json(self):
        """Json dictionary if request mime type is JSON.

        Json types is defined in Application.json_mime_types, typical is
        ``application/json`` and request method must be POST, PUT or PATCH and
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
        """Value of ``poor_Debug`` variable."""
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
        """Request scheme, typical ``http`` or ``https``."""
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
        """Server admin if set, or ``webmaster@hostname``."""
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
        """Alias for ``server_port`` property."""
        return int(self.__environ.get('SERVER_PORT'))

    @property
    def server_protocol(self):
        """Server protocol, as given by the client.

        In ``HTTP/0.9``. cgi ``SERVER_PROTOCOL`` value.
        """
        return self.__environ.get('SERVER_PROTOCOL')

    @property
    def protocol(self):
        """Alias for ``server_protocol`` property"""
        return self.__environ.get('SERVER_PROTOCOL')

    @property
    def forwarded_for(self):
        """``X-Forward-For`` http header if exists."""
        return self.__environ.get('HTTP_X_FORWARDED_FOR')

    @property
    def forwarded_host(self):
        """``X-Forward-Host`` http header if exists."""
        return self.__environ.get('HTTP_X_FORWARDED_HOST')

    @property
    def forwarded_proto(self):
        """``X-Forward-Proto`` http header if exists."""
        return self.__environ.get('HTTP_X_FORWARDED_PROTO')

    @property
    def secret_key(self):
        """Value of ``poor_SecretKey`` variable.

        Secret key is used by PoorSession class. It is generate from
        some server variables, and the best way is set programmatically
        by Application.secret_key from random data.
        """
        return self.__poor_environ.get(
            'poor_SecretKey',
            self.__app_config['secret_key'])

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
    def document_root(self):
        """Returns DocumentRoot setting."""
        return self.__poor_environ.get(
            'poor_DocumentRoot',
            self.__app_config['document_root'])

    @property
    def data(self):
        """Returns input data from wsgi.input file.

        This works only, when auto_data configuration and Content-Length of
        request are lower then input_cache configuration value. Other requests
        like big file data uploads increase memory and time system requests.
        """
        if isinstance(self.__file, BytesIO):
            try:
                self.__file.seek(0)
                return self.__file.read()
            finally:
                self.__file.seek(0)

    @property
    def input(self):
        """Return input file, for internal use in FieldStorage"""
        return self.__file

    @property
    def config(self):
        """For config object (default None)."""
        return self.__config

    @config.setter
    def config(self, value):
        self.__config = value

    @property
    def user(self):
        """For user object, who is login for example (default None)."""
        return self.__user

    @user.setter
    def user(self, value):
        self.__user = value

    # -------------------------- Methods --------------------------- #
    def __read(self, length=-1):
        return self.__file.read(length)

    def read(self, length=-1):
        """Read data from client (typical for XHR2 data POST).

        If length is not set, or if is lower then zero, Content-Length was
        be use.
        """
        if self.__content_length <= 0:
            log.error("No Content-Length found, read was failed!")
            return b''
        if length > -1 and length < self.__content_length:
            self.read = self.__read
            return self.read(length)
        return self.__file.read(self.__content_length)
    # enddef

    def get_options(self):
        """Returns dictionary with application variables from environment.

        Application variables start with ``app_`` prefix, but in returned
        dictionary is set without this prefix.

        .. code:: ini

            poor_Debug = on             # Poor WSGI variable
            app_db_server = localhost   # application variable db_server
            app_templates = app/templ   # application variable templates
        """
        options = {}
        for key, val in self.__poor_environ.items():
            key = key.strip()
            if key[:4].lower() == 'app_':
                options[key[4:].lower()] = val.strip()
        return options

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

    def __del__(self):
        log.debug("Request: Hasta la vista, baby.")
# endclass


class EmptyForm(dict):
    """Compatibility class as fallback."""
    def getvalue(self, key, default=None):
        return default

    def getfirst(self, key, default=None, fce=str):
        return fce(default) if default is not None else default

    def getlist(self, key, fce=str):
        return
        yield


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

    def getfirst(self, key, default=None, fce=str):
        """Returns first variable value for key or default.

        fce : convertor (str)
            function which processed value.
        """
        val = self.get(key, default)
        if val is None:
            return None

        if isinstance(val, list):
            return fce(val[0])
        return fce(val)

    def getlist(self, key, fce=str):
        """Returns list of variable values for key or empty list.

        fce : convertor (str)
            function which processed value.
        """
        val = self.get(key, None)
        if val is None:
            return

        if isinstance(val, list):
            for it in val:
                yield fce(it)
        else:
            yield fce(val)


class Json(dict):
    """Compatibility class for read values from JSON POST, PUT or PATCH request.

    It has getfirst and getlist methods, which can call function on values.
    """
    def __init__(self, req, charset):
        dict.__init__(self, json_loads(req.read().decode(charset)).items())
        self.getvalue = self.get

    def getfirst(self, key, default=None, fce=str):
        """Returns first variable value for key or default, if key not exist.

        default : any
            Default value if key not exists.
        fce : convertor
            Function which processed value.
        """
        val = self.get(key, default)
        if val is None:
            return None

        if isinstance(val, list):
            return fce(val[0])
        return fce(val)

    def getlist(self, key, fce=str):
        """Returns generoator of variable values for key.

        fce : convertor (str)
            Function which processed value.
        """
        val = self.get(key, None)
        if val is None:
            return

        if isinstance(val, list):
            for it in val:
                yield fce(it)
        else:
            yield fce(val)


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

    :name:      variable name, the same name from input attribute.
    :type:      mime-type of variable. All variables have internal
                mime-type, if that is no file, mime-type is text/plain.
    :filename:  if variable is file, filename is its name from form.
    :file:      file type instance, from you can read variable. This instance
                could be TemporaryFile as default for files, StringIO for
                normal variables or instance of your own file type class,
                create from file_callback.
    :lists:     if variable is list of variables, this contains instances of
                FieldStorage.
    """
    def __init__(self, req, headers=None, outerboundary=b'', environ=None,
                 keep_blank_values=0, strict_parsing=0, limit=None,
                 encoding='utf-8', errors='replace', file_callback=None):
        """Constructor of FieldStorage.

        Many of input parameters are need only for next internal use, because
        FieldStorage parse variables recursive. You need add only:

        req : Request
            Input request.
        keep_blank_values : int (0)
            If you want to parse blank values as right empty values.
        strict_parsing : int (0)
            If you want to raise exception on parsing error.
        file_callback : callback
            Callback for creating instance of uploading files.
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

            headers = req.headers
            req = req.input
        if environ is None:
            environ = {}

        self.environ = environ
        CgiFieldStorage.__init__(self, req, headers, outerboundary,
                                 environ, keep_blank_values,
                                 strict_parsing, limit, encoding, errors)
    # enddef

    def make_file(self, binary=None):
        """Return readable and writable temporary file.

        Arguments:
            binary : None
                Unused. Here is only for backward compatibility
        """
        if 'wsgi.file_callback' in self.environ:
            return self.environ['wsgi.file_callback'](self.filename)
        else:
            return CgiFieldStorage.make_file(self)

    def get(self, key, default=None):
        """Compatibility methods with dict, alias for getvalue."""
        return self.getvalue(key, default)

    def getfirst(self, key, default=None, fce=str):
        """Returns first variable value for key or default, if key not exist.

        Arguments:
            key : str
                key name
            default : None
                default value if key not found
            fce : convertor (str)
                Function or class which processed value.
        """
        val = CgiFieldStorage.getfirst(self, key, default)
        if val is None:
            return None
        return fce(val)

    def getlist(self, key, fce=str):
        """Returns list of variable values for key or empty list.

        Arguments:
            key : str
                key name
            fce : convertor (str)
                Function or class which processed value.
        """
        val = CgiFieldStorage.getlist(self, key)
        for it in val:
            yield fce(it)
# endclass
