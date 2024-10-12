"""Classes, which is used for managing requests.

:Classes:   SimpleRequest, Request, EmptyForm, Args, Json
"""
# pylint: disable=too-many-lines

import os
import re
import warnings
from http.cookies import SimpleCookie
from io import BytesIO
from json import loads as json_loads
from logging import getLogger
from time import time
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, unquote

from poorwsgi import fieldstorage
from poorwsgi.headers import Headers, parse_header, parse_negotiation
from poorwsgi.response import HTTPException
from poorwsgi.state import HTTP_BAD_REQUEST, methods

log = getLogger("poorwsgi")

# simple regular expression for construct_url method
RE_HTTPURLPATTERN = re.compile(r"^(http|https):\/\/")
RE_AUTHORIZATION = re.compile(r'(\w+\*?)[=] ?("[^"]+"|[\w\-\'%]+)')

# pylint: disable=unsubscriptable-object


class SimpleRequest:
    """Request proxy properties implementation - for internal use only."""
    # pylint: disable=too-many-public-methods
    def __init__(self, environ, app):
        self.__environ = environ
        self.__app = app

        # The path portion of the URI.
        self.__uri_rule = None

        # Reference to final uri_handler, user can use some uri_handler
        # attributes
        self.__uri_handler = None

        # Reference to error handler if exist.
        self.__error_handler = None

        # uwsgi do not sent environ variables to apps environ
        if 'uwsgi.version' in self.__environ or 'poor.Version' in os.environ:
            self.__poor_environ = os.environ
        else:
            self.__poor_environ = self.__environ

        var = self.__poor_environ.get('poor_Debug')
        if var:
            self.__debug = var.lower() == 'on'
        else:
            self.__debug = app.debug

        self.__start_time = environ['REQUEST_STARTTIME']
        self.__end_time = time()

    @property
    def debug(self):
        """Value of ``poor_Debug`` variable."""
        return self.__debug

    @property
    def app(self):
        """Return Application object which was created Request."""
        return self.__app

    @property
    def environ(self):
        """Copy of table object containing request environment.

        Information is get from wsgi server.
        """
        return self.__environ.copy()

    @property
    def poor_environ(self):
        """Environ with ``poor_`` variables.

        It is environ from request, or os.environ
        """
        return self.__poor_environ.copy()

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
    def uri_rule(self, value: str):
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
    def uri_handler(self, value: Callable):
        if self.__uri_handler is None:
            self.__uri_handler = value

    @property
    def error_handler(self):
        """This property is set only when error handler was called.

        It was set by Application object when error handler is known before
        calling.
        """
        return self.__error_handler

    @error_handler.setter
    def error_handler(self, value: Callable):
        if self.__error_handler is None:
            self.__error_handler = value

    @property
    def hostname(self):
        """Host, as set by full URI or Host: header without port."""
        return self.__environ.get('HTTP_HOST',
                                  self.server_hostname).split(':')[0]

    @property
    def host_port(self):
        """Port, as set by full URI or Host."""
        host = self.__environ.get('HTTP_HOST', '')
        if ':' in host:
            return int(host.split(':')[1])
        if self.server_scheme == 'https':
            return 443
        return 80

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
        """Deprecated alias for path of the URI."""
        return self.path

    @property
    def path(self):
        """Path part of url."""
        return self.__environ.get('PATH_INFO').encode('iso-8859-1').decode()

    @property
    def query(self):
        """The QUERY_STRING environment variable."""
        return self.__environ.get('QUERY_STRING', '').strip()

    @property
    def full_path(self):
        """Path with query, if it exist, from url."""
        query = self.query
        return self.path + ('?'+query if query else '')

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
        soft = self.__environ.get('SERVER_SOFTWARE', 'Unknown')
        if soft == 'Unknown' and 'uwsgi.version' in self.__environ:
            soft = 'uWsgi'
        return soft

    @property
    def server_admin(self):
        """Server admin if set, or ``webmaster@hostname``."""
        return self.__environ.get('SERVER_ADMIN',
                                  f'webmaster@{self.hostname}')

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
        """``X-Forward-Host`` http header without port if exists."""
        host = self.__environ.get('HTTP_X_FORWARDED_HOST')
        if host:
            host = host.split(':')[0]
        return host

    @property
    def forwarded_port(self):
        """Port from ``X-Forward-Host`` or ``X-Forward-Proto`` header."""
        host = self.__environ.get('HTTP_X_FORWARDED_HOST')
        if host and ':' in host:
            return int(host.split(':')[1])
        proto = self.forwarded_proto
        if proto == 'https':
            return 443
        if proto == 'http':
            return 80
        return None

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
            self.__app.secret_key)

    @property
    def document_index(self):
        """Value of poor_DocumentIndex variable.

        Variable is used to generate index html page, when poor_DocumentRoot
        is set.
        """
        var = self.__poor_environ.get('poor_DocumentIndex')
        if var:
            return var.lower() == 'on'
        return self.__app.document_index

    @property
    def document_root(self):
        """Returns DocumentRoot setting."""
        return self.__poor_environ.get(
            'poor_DocumentRoot',
            self.__app.document_root)

    @property
    def start_time(self):
        """Return timestamp when http request starts."""
        return self.__start_time

    @property
    def end_time(self):
        """Return timestamp when Request was created (end of __init__)."""
        return self.__end_time

    def get_options(self):
        """Returns dictionary with application variables from environment.

        Application variables start with ``app_`` prefix, but in returned
        dictionary is set without this prefix.

        .. code:: ini

            poor_Debug = on             # Poor WSGI variable
            app_db_server = localhost   # application variable db_server
            app_templates = app/templ   # application variable templates
        """
        warnings.warn("Call to deprecated Request.get_options."
                      "Use Application.get_options instead.",
                      category=DeprecationWarning,
                      stacklevel=1)

        options = {}
        for key, val in self.__poor_environ.items():
            key = key.strip()
            if key[:4].lower() == 'app_':
                options[key[4:].lower()] = val.strip()
        return options

    def construct_url(self, uri: str):
        """This function returns a fully qualified URI string.

        Url is create from the path specified by uri, using the information
        stored in the request to determine the scheme, server host name
        and port. The port number is not included in the string if it is the
        same as the default port 80."""

        if not RE_HTTPURLPATTERN.match(uri):
            scheme = self.forwarded_proto or self.server_scheme
            host = self.forwarded_host or self.hostname
            port = self.forwarded_port or self.host_port
            if not ((port == 80 and scheme == 'http') or
                    (port == 443 and scheme == 'https')):
                return f"{scheme}://{host}:{port}{uri}"
            return f"{scheme}://{host}{uri}"
        return uri


class Request(SimpleRequest):
    """HTTP request object with all server elements.

    It could be compatible as soon as possible with mod_python.apache.request.
    Special variables for user use are prefixed with ``app_``.
    """
    # pylint: disable=too-many-public-methods

    def __init__(self, environ, app):
        """Object was created automatically in wsgi module.

        It's input parameters are the same, which Application object gets from
        WSGI server plus file callback for auto request body parsing.
        """
        # pylint: disable=too-many-branches, too-many-statements
        super().__init__(environ, app)

        if environ.get('PATH_INFO') is None:
            raise ConnectionError(
                "PATH_INFO not set, probably bad HTTP protocol used.")

        # A table object containing headers sent by the client.
        tmp = []
        for key, val in environ.items():
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
        self.__authorization = None

        self.__file = environ.get("wsgi.input")
        self._errors = environ.get("wsgi.errors")

        if app.auto_data and \
                0 <= self.__content_length <= app.data_size:
            self.__file = BytesIO(self.__file.read(self.__content_length))
            self.__file.seek(0)

        self.__cached_size = app.cached_size
        self.__cached_input = None
        self.__read_timeout = app.read_timeout

        # path args are set via wsgi.handler_from_table
        self.__path_args = None

        # args
        if app.auto_args:
            self.__args = Args(self, app.keep_blank_values,
                               app.strict_parsing)
        else:
            self.__args = EmptyForm()

        # test auto json parsing
        if app.auto_json and \
                (self.is_body_request or self.server_protocol == "HTTP/0.9") \
                and self.__mime_type in app.json_mime_types:
            self.__json = parse_json_request(self.read(), self.__charset)
            self.__form = EmptyForm()
        # test auto form parsing
        elif app.auto_form and \
                (self.is_body_request or self.server_protocol == "HTTP/0.9") \
                and self.__mime_type in app.form_mime_types:
            form_parser = fieldstorage.FieldStorageParser(
                self.input, self.headers,
                keep_blank_values=app.keep_blank_values,
                strict_parsing=app.strict_parsing,
                file_callback=app.file_callback)
            self.__form = form_parser.parse()
            self.__json = EmptyForm()
        else:
            self.__form = EmptyForm()
            self.__json = EmptyForm()

        if app.auto_cookies and 'Cookie' in self.__headers:
            self.__cookies = SimpleCookie()
            self.__cookies.load(self.__headers['Cookie'])
        else:
            self.__cookies = None

        # variables for user use
        self.__user = None
        self.__api = None
        self.__db = None

        # ugly hack
        # pylint: disable=invalid-name
        self._SimpleRequest__end_time = time()
    # enddef

    # -------------------------- Properties --------------------------- #
    @property
    def mime_type(self) -> str:
        """Request ``Content-Type`` header or empty string if not set."""
        return self.__mime_type

    @property
    def charset(self) -> str:
        """Request ``Content-Type`` charset header string, utf-8 if not set."""
        return self.__charset

    @property
    def content_length(self) -> int:
        """Request ``Content-Length`` header value, -1 if not set."""
        return self.__content_length

    @property
    def headers(self):
        """Reference to input headers object."""
        return self.__headers

    @property
    def accept(self) -> tuple:
        """Tuple of client supported mime types from Accept header."""
        if self.__accept is None:
            self.__accept = tuple(parse_negotiation(
                self.__headers.get("Accept", '')))
        return self.__accept

    @property
    def accept_charset(self) -> tuple:
        """Tuple of client supported charset from Accept-Charset header."""
        if self.__accept_charset is None:
            self.__accept_charset = tuple(parse_negotiation(
                self.__headers.get("Accept-Charset", '')))
        return self.__accept_charset

    @property
    def accept_encoding(self) -> tuple:
        """Tuple of client supported charset from Accept-Encoding header."""
        if self.__accept_encoding is None:
            self.__accept_encoding = tuple(parse_negotiation(
                self.__headers.get("Accept-Encoding", '')))
        return self.__accept_encoding

    @property
    def accept_language(self) -> tuple:
        """List of client supported languages from Accept-Language header."""
        if self.__accept_language is None:
            self.__accept_language = tuple(parse_negotiation(
                self.__headers.get("Accept-Language", '')))
        return self.__accept_language

    @property
    def accept_html(self) -> bool:
        """Return true if ``text/html`` mime type is in accept negotiations
           values.
        """
        return "text/html" in dict(self.accept)

    @property
    def accept_xhtml(self) -> bool:
        """Return true if ``text/xhtml`` mime type is in accept negotiations
           values.
        """
        return "text/xhtml" in dict(self.accept)

    @property
    def accept_json(self) -> bool:
        """Return true if ``application/json`` mime type is in accept
           negotiations values.
        """
        return "application/json" in dict(self.accept)

    @property
    def authorization(self) -> dict:
        """Return Authorization header parsed to dictionary."""
        if self.__authorization is None:
            auth = self.__headers.get('Authorization', '').strip()
            self.__authorization = dict(
                (key, Headers.utf8(val.strip('"'))) for key, val in
                RE_AUTHORIZATION.findall(auth))
            self.__authorization['type'] = auth[:auth.find(' ')].capitalize()
            username_ = self.__authorization.get('username*')
            if username_ and username_.startswith("UTF-8''"):
                self.__authorization['username'] = unquote(username_[7:])
        return self.__authorization.copy()

    @property
    def is_xhr(self) -> bool:
        """If ``X-Requested-With`` header is set with ``XMLHttpRequest`` value.
        """
        return self.__headers.get('X-Requested-With') == 'XMLHttpRequest'

    @property
    def is_body_request(self) -> bool:
        """True if has set Content-Length more than zero."""
        return self.__content_length > 0

    @property
    def is_chunked(self) -> bool:
        """True if has set Transfer-Encoding is chunked."""
        return self.__headers.get('Transfer-Encoding') == 'chunked'

    @property
    def is_chunked_request(self):
        """Compatibility alias for is_chunked."""
        warnings.warn("Call to deprecated is_chunked_request, "
                      "use is_chunked instead",
                      category=DeprecationWarning,
                      stacklevel=1)
        return self.is_chunked

    @property
    def path_args(self) -> dict:
        """Dictionary arguments from path of regual expression rule."""
        return (self.__path_args or {}).copy()

    @path_args.setter
    def path_args(self, value: str):
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
    def args(self, value: 'Args'):
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
    def form(self, value: fieldstorage.FieldStorage):
        if isinstance(self.__form, EmptyForm):
            self.__form = value

    @property
    def json(self):
        """Json dictionary if request mime type is JSON.

        Json types is defined in Application.json_mime_types, typical is
        ``application/json`` and request method must be POST, PUT or PATCH and
        Application.auto_json must be set to true (default). Otherwise json
        is EmptyForm.

        When request data is present, that will by parsed with
        parse_json_request function.
        """
        return self.__json

    @property
    def cookies(self):
        """SimpleCookie iterable object of all cookies from Cookie header.

        This property was set if Application.auto_cookies is set to true,
        which is default. Otherwise cookies is None.
        """
        return self.__cookies

    @property
    def data(self):  # pylint: disable=inconsistent-return-statements
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
        if self.__cached_input:
            return self.__cached_input
        if not self.__cached_size or isinstance(self.__file, BytesIO):
            return self.__file
        self.__cached_input = CachedInput(self.__file,
                                          self.content_length,
                                          self.__cached_size,
                                          self.__read_timeout)
        return self.__cached_input

    @property
    def user(self):
        """For user object, who is login for example (default None)."""
        return self.__user

    @user.setter
    def user(self, value):
        self.__user = value

    @property
    def api(self):
        """For api request object, could be used for OpenAPIRequest."""
        return self.__api

    @api.setter
    def api(self, value):
        self.__api = value

    @property
    def db(self):
        """For api request object, could be used for database connection(s)."""
        return self.__db

    @db.setter
    def db(self, value):
        self.__db = value

    # -------------------------- Methods --------------------------- #
    def __read(self, length: int = -1):
        return self.__file.read(length)

    def read(self, length=-1):  # pylint: disable=method-hidden
        """Read data from client (typical for XHR2 data POST).

        If length is not set, or if is lower then zero, Content-Length was
        be use.
        """
        if not self.is_body_request and self.server_protocol != "HTTP/0.9":
            log.error("No Content-Length found, read was failed!")
            return b''
        if -1 < length < self.__content_length:
            self.read = self.__read
            return self.read(length)
        return self.__file.read(self.__content_length)

    def read_chunk(self):
        """Read chunk when Transfer-Encoding is `chunked`.

        Method read line with chunk size first, then read chunk and return it,
        or raise ValueError when chunk size is in bad format.

        Be sure that wsgi server allow readline from wsgi.input. For examples
        uWSGI has extra API
        https://uwsgi-docs.readthedocs.io/en/latest/Chunked.html
        """
        size = int(self.__file.readline(), base=16)
        try:
            return self.__file.read(size)
        finally:
            self.__file.readline()  # skip new line after chunk

    def __del__(self):
        log.debug("Request: Hasta la vista, baby.")


class EmptyForm(dict, fieldstorage.FieldStorageInterface):
    """Compatibility class as fallback."""
    # pylint: disable=unused-argument
    def getvalue(self, key: str, default: Any = None,
                 func: Callable = lambda x: x):
        """Just return default."""
        return default

    def getfirst(self, key: str, default: Any = None,
                 func: Callable = lambda x: x,
                 fce: Optional[Callable] = None):
        """Just return default."""
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
        return default

    def getlist(self, key: str, default: Any = None,
                func: Callable = lambda x: x,
                fce: Optional[Callable] = None):
        """Just return default or empty list."""
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
        return default or []


class Args(dict, fieldstorage.FieldStorageInterface):
    """Compatibility class for read values from QUERY_STRING.

    Class is based on dictionary. It has getfirst and getlist methods,
    which can call function on values.
    """
    def __init__(self, req: Request, keep_blank_values=0, strict_parsing=0):
        query = req.query
        args = parse_qs(
            query, keep_blank_values, strict_parsing) if query else {}
        dict.__init__(self, ((key, val[0] if len(val) < 2 else val)
                             for key, val in args.items()))


class JsonDict(dict, fieldstorage.FieldStorageInterface):
    """Compatibility class for read values from JSON POST, PUT or PATCH
    request.

    It has getfirst and getlist methods, which can call function on values.

    **Deprecated:** this class will be deleted in next major version.

    >>> json = JsonDict({"key": "42"})
    >>> json.getvalue("key", func=int)
    42

    >>> json = JsonDict({"key": ["42", "15"]})
    >>> json.getlist("key", func=int)
    [42, 15]

    >>> json.getfirst("key", func=int)
    42
    """


class JsonList(list):
    """Compatibility class for read values from JSON POST, PUT or PATCH
    request.

    It has getfirst and getlist methods, which can call function on values.

    **Deprecated:** this class will be deleted in next major version.
    """

    # pylint: disable=unused-argument
    def getvalue(self, key=None, default: Any = None,
                 func: Callable = lambda x: x):
        """Returns first item or defualt if no exists.

        key : None
            Compatibility parametr is ignored.
        default : any
            Default value if key not exists.
        func : converter (lambda x: x)
                Function or class which processed value. Default type of value
                is bytes for files and string for others.
        """
        return func(self[0]) if self else default

    def getfirst(self, key=None, default: Any = None,
                 func: Callable = lambda x: x,
                 fce: Optional[Callable] = None):
        """Returns first variable value or default, if no one exist.

        key : None
            Compatibility parametr is ignored.
        default : any
            Default value if key not exists.
        func : converter
            Function which processed value.
        fce : deprecated converter name
            Use func converter just like getvalue.
        """
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
            func = fce

        return self.getvalue(default=default, func=func)

    def getlist(self, key: str, default: Optional[list] = None,
                func: Callable = lambda x: x,
                fce: Optional[Callable] = None):
        """Returns list of values

        key : None
            Compatibility parametr is ignored.
        default : list
            Default value when self is empty.
        func : converter
            Function which processed value.
        fce : deprecated converter name
            Use func converter just like getvalue.
        """
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
            func = fce

        if not self:
            return default or []
        return [func(x) for x in self]


# pylint: disable=inconsistent-return-statements
def parse_json_request(raw: bytes, charset: str = "utf-8"):
    """Try to parse request data.

    Returned type could be:

    * JsonDict when dictionary is parsed.
    * JsonList when list is parsed.
    * Other based types from json.loads function like str, int, float, bool
      or None.
    * None when parsing of JSON fails. That is logged with WARNING log level.

    """
    # pylint: disable=inconsistent-return-statements
    try:
        data = json_loads(raw.decode(charset))
        if isinstance(data, dict):
            return JsonDict(data.items())
        if isinstance(data, list):
            return JsonList(data)
        return data
    except BaseException as err:  # pylint: disable=broad-except
        log.error("Invalid request json: %s", str(err))
        raise HTTPException(HTTP_BAD_REQUEST, error=err) from err


def FieldStorage(req=Request,  # noqa: N802
                 headers=None,
                 keep_blank_values=0, strict_parsing=0,
                 encoding='utf-8', errors='replace',
                 max_num_fields=None, separator='&', file_callback=None):
    """**Deprecated:**  back compatibility function.

    This function will be deleted in next major version.

    Use direct FieldStorageParser instead of this!.
    """
    # pylint: disable=unused-argument
    # pylint: disable=invalid-name

    warnings.warn("Call to deprecated FieldStorage parsing method."
                  "Use fieldstorage.FieldStorageParser instead.",
                  category=DeprecationWarning, stacklevel=1)

    form_parser = fieldstorage.FieldStorageParser(
                req.input, req.headers,
                keep_blank_values=keep_blank_values,
                strict_parsing=strict_parsing,
                encoding=encoding,
                errors=errors,
                max_num_fields=max_num_fields,
                separator=separator,
                file_callback=file_callback)
    return form_parser.parse()


class CachedInput:
    """
    Wrapper around wsgi.input file, which reads data block by block.

    timeout : float
        how long to wait for new bytes in seconds
    """
    def __init__(self, file, size, block_size=32768,
                 timeout: Optional[float] = 10.):
        self.__file = file
        self.__buffer = b''
        self.__todo = size
        self.__timeout = timeout
        self.block_size = block_size

    def read(self, size=-1):
        """Compatible file read which works with internal buffer."""
        if size < 0:
            size = self.block_size

        b_size = len(self.__buffer)
        size = min(self.__todo, size)

        if self.__buffer:
            if b_size >= size:
                retval = self.__buffer[:size]
                self.__buffer = self.__buffer[size:]
                return retval
            size = size - b_size
            self.__todo -= size
            retval = self.__buffer + self.__file.read(size)
            self.__buffer = b''
            return retval

        size = min(self.__todo, size)
        self.__todo -= size
        return self.__file.read(size)

    def readline(self, size=-1):  # noqa: C901
        """Compatible file read which works with internal buffer."""
        if size < 0:
            size = self.block_size

        if not self.__buffer:
            size = min(self.__todo, size)
            self.__todo -= size
            self.__buffer = self.__file.read(size)

        line = b''
        l_size = 0
        if self.__timeout is not None:
            times_out_at = time() + self.__timeout
            seen_data = False

        while l_size < size:
            max_size = size-l_size
            pos = self.__buffer.find(b'\r\n', 0, max_size)
            if pos >= 0:
                line += self.__buffer[:pos + 2]
                self.__buffer = self.__buffer[pos + 2:]
                return line

            if self.__timeout is not None:
                if self.__buffer:
                    seen_data = True
                elif seen_data:
                    seen_data = False
                    times_out_at = time() + self.__timeout
                elif time() > times_out_at:
                    raise TimeoutError("Timed out while receiving data")

            line += self.__buffer[:max_size]
            self.__buffer = self.__buffer[max_size:]
            l_size = len(line)

            if l_size < size:
                n_size = min(self.__todo, max_size)
                self.__todo -= n_size
                self.__buffer = self.__file.read(n_size)

        # no end-of-line found
        return line
