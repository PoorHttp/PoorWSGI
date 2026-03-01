"""Application callable class, which is the main entry point for a WSGI
application.

:Classes:   Application
:Functions: to_response

"""
# pylint: disable=too-many-lines
# pylint: disable=unsubscriptable-object
# pylint: disable=consider-using-f-string

import re
import uuid
from collections import OrderedDict
from hashlib import md5, sha256
from logging import getLogger
from os import R_OK, access, environ, path
from time import time
from typing import Callable, ClassVar, Optional, Type, Union

from poorwsgi.request import Request, SimpleRequest
from poorwsgi.response import (
    BaseResponse,
    FileObjResponse,
    FileResponse,
    HTTPException,
    ResponseError,
    make_response,
)
from poorwsgi.results import (
    debug_info,
    default_states,
    directory_index,
    internal_server_error,
    not_implemented,
)
from poorwsgi.state import (
    HTTP_FORBIDDEN,
    HTTP_METHOD_NOT_ALLOWED,
    HTTP_NOT_FOUND,
    METHOD_GET,
    METHOD_HEAD,
    METHOD_POST,
    deprecated,
    methods,
)

log = getLogger("poorwsgi")

# check, if there is define filter in uri
re_filter = re.compile(r"<(\w+)(:[^>]+)?>")

# check for invalid route definitions with spaces
# Matches: <{space}name, <name{space}: , <name{space}> , <name:{space}word,
# <name:filter{space}>
re_invalid_filter = re.compile(
    r"<\s+\w+|<\w+\s+[:|>]|<\w+:\s+\w+|<\w+:[^>]+\s+>"
)

# Supported authorization algorithms
AUTH_DIGEST_ALGORITHMS = {
    "MD5": md5,
    "MD5-sess": md5,
    "SHA-256": sha256,
    "SHA-256-sess": sha256,
    # 'SHA-512-256': sha512,  # Need extend library
    # 'SHA-512-256-sess': sha512,
}


def to_response(response):
    """Converts a handler's response to an application response."""
    if isinstance(response, BaseResponse):
        return response

    if not isinstance(response, tuple):
        response = (response,)
    return make_response(*response)


class Application:
    """Poor WSGI application that is called by the WSGI server.

    Its working is described in PEP 0333. This object stores the route
    dispatch table, and has methods for its use, as well as a __call__
    method for use as a WSGI application.
    """

    # pylint: disable=too-many-public-methods
    __instances: ClassVar[list[str]] = []

    def __init__(self, name="__main__"):
        """The Application class is a per-name singleton.

        That means, there can only be one instance with the same name.
        """
        if Application.__instances.count(name):
            raise RuntimeError("Application with name %s exist yet." % name)
        Application.__instances.append(name)

        # Application name
        self.__name = name

        # list of pre and post process handlers
        self.__before = []
        self.__after = []

        # dhandlers table for default handers on methods {METHOD_GET: handler}
        self.__dhandlers = {}

        # handlers table of simple paths: {'/path': {METHOD_GET: handler}}
        self.__handlers = {}

        self.__filters = {
            ":int": (r"-?\d+", int),
            ":float": (r"-?\d+(\.\d+)?", float),
            ":word": (r"\w+", str),
            ":hex": (r"[0-9a-fA-F]+", str),
            ":uuid": (
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                uuid.UUID,
            ),
            ":re:": (None, str),
            "none": (r"[^/]+", str),
        }

        # handlers of regex paths: {r'/user/([a-z]?)': {METHOD_GET: handler}}
        self.__rhandlers = OrderedDict()

        # http state handlers: {HTTP_NOT_FOUND: {METHOD_GET: my_404_handler}}
        self.__shandlers = {}

        # exception handlers: {ValueError: {METHOD_GET: my_value_handler}}
        self.__ehandlers = OrderedDict()

        # -- Application variable
        self.__config = {
            "auto_args": True,
            "auto_form": True,
            "auto_json": True,
            "auto_data": True,
            "cached_size": 65365,
            "data_size": 65365,
            "read_timeout": 10,
            "keep_blank_values": 0,
            "strict_parsing": 0,
            "file_callback": None,
            "json_mime_types": [
                "application/json",
                "application/javascript",
                "application/merge-patch+json",
            ],
            "form_mime_types": [
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            "auto_cookies": True,
            "debug": "Off",
            "document_root": "",
            "document_index": "Off",
            "secret_key": None,  # nosec
            "auth_type": None,
            "auth_algorithm": "MD5-sess",
            "auth_qop": "auth",
            "auth_timeout": 300,
        }
        self.__auth_hash = md5

        # authorization map object
        self.auth_map = {}

        # profile attributes
        self.__runctx = None
        self.__dump = None
        self.__original_request__ = None

    def __regex(self, match):
        groups = match.groups()
        _filter = str(groups[1]).lower()

        if _filter in self.__filters:
            regex = self.__filters[_filter][0]
        elif _filter[:4] == ":re:":  # :re: filter have user defined regex
            regex = _filter[4:]
        else:
            try:
                regex = self.__filters[_filter][0]
            except KeyError as err:
                raise RuntimeError(
                    "Undefined route group filter '%s'" % _filter
                ) from err

        return "(?P<%s>%s)" % (groups[0], regex)

    def __converter(self, _filter):
        _filter = str(_filter).lower()
        _filter = ":re:" if _filter[:4] == ":re:" else _filter
        try:
            return self.__filters[_filter][1]
        except KeyError as err:
            raise RuntimeError(
                "Undefined route group filter '%s'" % _filter
            ) from err

    @property
    def name(self):
        """Returns the application name."""
        return self.__name

    @property
    def filters(self):
        """A copy of the filter table.

        The filter table contains regular expressions and conversion functions;
        see Application.set_filter and Application.route.

        Default filters are:

            **:int**    matches a number and converts it to an int

            **:float**  matches a number and converts it to a float

            **:word**   matches a single string word

            **:hex**    matches a hexadecimal value and converts it to a str

            **:re:**    matches a user-defined regular expression

            **none**    matches any string without the '/' character

        For more details, see the `/debug-info` page of your application,
        where you can find all filters with their regular expression
        definitions.
        """
        return self.__filters.copy()

    @property
    def before(self):
        """A tuple of before-response handlers.

        See Application.before_response.
        """
        return tuple(self.__before)

    @property
    def after(self):
        """A tuple of after-response handlers.

        See Application.after_response.
        """
        return tuple(self.__after)

    @property
    def defaults(self):
        """A copy of the table with default handlers.

        See Application.set_default.
        """
        return self.__dhandlers.copy()

    @property
    def routes(self):
        """A copy of the table with static handlers.

        See Application.route.
        """
        return self.__handlers.copy()

    @property
    def regular_routes(self):
        """A copy of the table with regular expression handlers.

        See Application.route and Application.regular_route.
        """
        return self.__rhandlers.copy()

    @property
    def states(self):
        """A copy of the table with HTTP state handlers.

        See Application.http_state.
        """
        return self.__shandlers.copy()

    @property
    def errors(self):
        """A copy of the table with exception handlers.

        See Application.error_handler.
        """
        return self.__ehandlers.copy()

    @property
    def auto_args(self):
        """Automatic parsing of request arguments from the URI.

        If it is True (default), the Request object automatically parses
        the request URI into its args variable.
        """
        return self.__config["auto_args"]

    @auto_args.setter
    def auto_args(self, value):
        self.__config["auto_args"] = bool(value)

    @property
    def auto_form(self):
        """Automatic parsing of arguments from the request body.

        If it is True (default) and the method is POST, PUT, or PATCH, and the
        request MIME type is one of form_mime_types, the Request
        object automatically parses the request body into its form variable.
        """
        return self.__config["auto_form"]

    @auto_form.setter
    def auto_form(self, value):
        self.__config["auto_form"] = bool(value)

    @property
    def auto_json(self):
        """Automatic parsing of JSON from the request body.

        If it is True (default), the method is POST, PUT, or PATCH, and
        the request MIME type is one of json_mime_types, the Request
        object automatically parses the request body into the json
        variable.
        """
        return self.__config["auto_json"]

    @auto_json.setter
    def auto_json(self, value):
        self.__config["auto_json"] = bool(value)

    @property
    def auto_data(self):
        """Enables the Request.data property for smaller requests.

        Default value is True.
        """
        return self.__config["auto_data"]

    @auto_data.setter
    def auto_data(self, value: Union[int, bool]):
        self.__config["auto_data"] = bool(value)

    @property
    def cached_size(self):
        """Enables cached_size for faster POST requests.

        Default value is 65365.
        """
        return self.__config["cached_size"]

    @cached_size.setter
    def cached_size(self, value: int):
        self.__config["cached_size"] = value

    @property
    def data_size(self):
        """Size limit for the Request.data property.

        This value is compared to the request's Content-Length. The
        default value is 32768 (30KB).
        """
        return self.__config["data_size"]

    @data_size.setter
    def data_size(self, value: int):
        self.__config["data_size"] = int(value)

    @property
    def auto_cookies(self):
        """Automatic parsing of cookies from request headers.

        If it is True (default) and the Cookie request header is set,
        a SimpleCookie object is parsed to the Request property cookies.
        """
        return self.__config["auto_cookies"]

    @auto_cookies.setter
    def auto_cookies(self, value: Union[int, bool]):
        self.__config["auto_cookies"] = bool(value)

    @property
    def debug(self):
        """Application debug mode, as another way to set poor_Debug.

        This setting will be overridden by the poor_Debug environment variable.
        """
        return self.__config["debug"] == "On"

    @debug.setter
    def debug(self, value: Union[int, bool]):
        self.__config["debug"] = "On" if bool(value) else "Off"

    @property
    def document_root(self):
        """The application's document_root, as another way to set
        poor_DocumentRoot.

        This setting will be overridden by the poor_DocumentRoot environment
        variable.
        """
        return self.__config["document_root"]

    @document_root.setter
    def document_root(self, value: str):
        self.__config["document_root"] = value

    @property
    def document_index(self):
        """The application's document_index, as another way to set
        poor_DocumentIndex.

        This setting will be overridden by the poor_DocumentIndex environment
        variable.
        """
        return self.__config["document_index"] == "On"

    @document_index.setter
    def document_index(self, value: Union[int, bool]):
        self.__config["document_index"] = "On" if bool(value) else "Off"

    @property
    def secret_key(self):
        """The application's secret_key can be overridden by poor_SecretKey in
        the request.

        The secret key is used by the PoorSession class. It is generated from
        some server variables; it is best to set it to your own long key."""
        return self.__config["secret_key"]

    @secret_key.setter
    def secret_key(self, value: Union[str, bytes]):
        self.__config["secret_key"] = value

    @property
    def keep_blank_values(self):
        """Keeps blank values in request arguments.

        If it is 1 (0 is default), automatic parsing of the request URI or body
        will keep blank values as empty strings.
        """
        return self.__config["keep_blank_values"]

    @keep_blank_values.setter
    def keep_blank_values(self, value: Union[int, bool]):
        self.__config["keep_blank_values"] = int(value)

    @property
    def strict_parsing(self):
        """Strict parsing of request arguments.

        If it is 1 (0 is default), automatic parsing of the request URI or body
        will raise an exception on a parsing error.
        """
        return self.__config["strict_parsing"]

    @strict_parsing.setter
    def strict_parsing(self, value: Union[int, bool]):
        self.__config["strict_parsing"] = int(value)

    @property
    def file_callback(self):
        """A file callback used as a parameter when parsing the request body.

        Default is None. The value can be a class or factory that receives a
        filename from the request body and has a file-compatible interface.
        """
        return self.__config["file_callback"]

    @file_callback.setter
    def file_callback(self, value: Callable):
        self.__config["file_callback"] = value

    @property
    def read_timeout(self):
        """Gets the timeout (in seconds) used for file reception."""
        return self.__config["read_timeout"]

    @read_timeout.setter
    def read_timeout(self, timeout: float):
        """Sets the timeout (in seconds) used for file reception."""
        self.__config["read_timeout"] = timeout

    @property
    def json_mime_types(self):
        """A copy of the JSON MIME type list.

        Contains a list of strings as JSON MIME types, which are used for
        testing when an automatic JSON object is created from the request body.
        """
        return self.__config["json_mime_types"]

    @property
    def auth_type(self):
        """Authorization type.

        Only the ``Digest`` type is currently supported.
        """
        return self.__config["auth_type"]

    @auth_type.setter
    def auth_type(self, value: str):
        value = value.capitalize()
        if value not in ("Digest",):
            raise ValueError("Unsupported authorization type")
        # for Digest
        if self.__config["secret_key"] is None:
            raise ValueError("Set secret key first")
        self.__config["auth_type"] = value

    @property
    def auth_algorithm(self):
        """Authorization algorithm.

        The algorithm depends on the authorization type and client support.
        Supported:

        :Digest: MD5 | MD5-sess | SHA256 | SHA256-sess
        :default: MD5-sess
        """
        return self.__config["auth_algorithm"]

    @auth_algorithm.setter
    def auth_algorithm(self, value: str):
        if self.__config["auth_algorithm"] is None:
            raise ValueError("Set authorization type first")

        if self.__config["auth_algorithm"] == "Digest":
            if value not in AUTH_DIGEST_ALGORITHMS:
                raise ValueError("Unsupported Digest algorithm")
        self.__config["auth_algorithm"] = value
        self.__auth_hash = AUTH_DIGEST_ALGORITHMS[value]

    @property
    def auth_hash(self):
        """Returns the authorization hash function.

        The function can be changed by the auth_algorithm property.

        :default: md5
        """
        return self.__auth_hash

    @property
    def auth_qop(self):
        """Authorization quality of protection.

        This is used for Digest authorization only. PoorWSGI supports only
        ``auth`` or an empty value, consistent with common browser support.

        :default: auth
        """
        return self.__config["auth_qop"]

    @auth_qop.setter
    def auth_qop(self, value: str):
        if value not in ("", "auth", None):
            raise ValueError("Unsupported quality of protection")
        self.__config["auth_qop"] = value

    @property
    def auth_timeout(self):
        """Digest Authorization timeout for the nonce value in seconds.

        In fact, the timeout will be between timeout and 2*timeout because
        time alignment is used. If timeout is None or 0, no timeout is used.

        :default: 300 (5 min)
        """
        return self.__config["auth_timeout"]

    @auth_timeout.setter
    def auth_timeout(self, value: Optional[int]):
        if not isinstance(value, (type(None), int)):
            raise ValueError("Unsupported auth_timeout value")
        self.__config["auth_timeout"] = value

    @property
    def form_mime_types(self):
        """A copy of the form MIME type list.

        Contains a list of strings as form MIME types, which are used for
        testing when an automatic Form object is created from the request body.
        """
        return self.__config["form_mime_types"]

    def set_filter(self, name: str, regex: str, converter: Callable = str):
        r"""Creates a new filter or overwrites built-ins.

        name
            The name of the filter used in the route or set_route method.
        regex
            The regular expression used for the filter.
        converter
            The converter function or class that takes a string as input.
            The default is the str function, which calls the __str__
            method on the input object.

        .. code:: python

            app.set_filter('uint', r'\d+', int)
        """
        name = ":" + name if name[0] != ":" else name
        self.__filters[name] = (regex, converter)

    @deprecated("use before_response instead")
    def before_request(self):
        """Deprecated; use before_response instead."""

        def wrapper(fun):
            self.add_before_response(fun)
            return fun

        return wrapper

    def before_response(self):
        """Appends a handler to call before each response.

        This is a decorator for a function to call before each response.

        .. code:: python

            @app.before_response()
            def before_each_response(req):
                print("Response coming")
        """

        def wrapper(fun):
            self.add_before_response(fun)
            return fun

        return wrapper

    @deprecated("use add_before_response instead")
    def add_before_request(self, fun: Callable):
        """Deprecated; use add_before_response instead."""
        self.add_before_response(fun)

    def add_before_response(self, fun: Callable):
        """Appends a handler to call before each response.

        This method adds a function to the list of functions that are
        called before each response.

        .. code:: python

            def before_each_response(req):
                print("Response coming")

            app.add_before_response(before_each_response)
        """
        if self.__before.count(fun):
            raise ValueError("%s is in list yet" % str(fun))
        self.__before.append(fun)

    @deprecated("use pop_before_response instead")
    def pop_before_request(self, fun: Callable):
        """Deprecated; use pop_before_response instead."""
        self.pop_before_response(fun)

    def pop_before_response(self, fun: Callable):
        """Removes a handler added by add_before_response or
        before_response."""
        if not self.__before.count(fun):
            raise ValueError("%s is not in list" % str(fun))
        self.__before.remove(fun)

    @deprecated("use after_response instead")
    def after_request(self):
        """Deprecated; use after_response instead."""

        def wrapper(fun):
            self.add_after_response(fun)
            return fun

        return wrapper

    def after_response(self):
        """Appends a handler to call after each response.

        This decorator appends a function to be called after each response.
        The handler must return a response object.

        .. code:: python

            @app.after_response()
            def after_each_response(request, response):
                print("Response out")
                return response
        """

        def wrapper(fun):
            self.add_after_response(fun)
            return fun

        return wrapper

    @deprecated("use add_after_response instead")
    def add_after_request(self, fun: Callable):
        """Deprecated; use add_after_response instead."""
        self.add_after_response(fun)

    def add_after_response(self, fun: Callable):
        """Appends a handler to call after each response.

        This method directly appends a function to the list of functions
        that are called after each response.

        .. code:: python

            def after_each_response(request, response):
                print("Response out")
                return response

            app.add_after_response(after_each_response)
        """
        if self.__after.count(fun):
            raise ValueError("%s is in list yet" % str(fun))
        self.__after.append(fun)

    @deprecated("use pop_after_response instead")
    def pop_after_request(self, fun: Callable):
        """Deprecated; use pop_after_response instead."""
        self.pop_after_response(fun)

    def pop_after_response(self, fun: Callable):
        """Removes a handler added by add_after_response or after_response."""
        if not self.__before.count(fun):
            raise ValueError("%s is not in list" % str(fun))
        self.__after.remove(fun)

    def default(self, method: int = METHOD_HEAD | METHOD_GET):
        """Sets a default handler.

        This is a decorator for a default handler for an HTTP method
        (called before error_not_found).

        .. code:: python

            @app.default(METHOD_GET_POST)
            def default_get_post(req):
                # Called if no URI matches in the internal URI table for
                # the method. Similar to a not_found error, but without
                # an error.
                ...
        """

        def wrapper(fun):
            self.set_default(fun, method)
            return fun

        return wrapper

    def set_default(
        self, fun: Callable, method: int = METHOD_HEAD | METHOD_GET
    ):
        """Sets a default handler.

        Sets ``fun`` as the default handler for the HTTP method, called before
        error_not_found.

        .. code:: python

            app.set_default(default_get_post, METHOD_GET_POST)
        """
        for val in methods.values():
            if method & val:
                self.__dhandlers[val] = fun

    def pop_default(self, method: int):
        """Pops the default handler for a method."""
        return self.__dhandlers.pop(method)

    def route(self, uri: str, method: int = METHOD_HEAD | METHOD_GET):
        r"""Wraps a function to be a handler for a URI and specified method.

        You can define the URI as a static path or with groups, which are
        passed to the handler as subsequent parameters.

        .. code:: python

            # static URI
            @app.route('/user/post', method=METHOD_POST)
            def user_create(req):
                ...

            # group regular expression
            @app.route('/user/<name>')
            def user_detail(req, name):
                ...

            # group regular expression with filter
            @app.route('/<surname:word>/<age:int>')
            def surnames_by_age(req, surname, age):
                ...

            # group with its own regular expression filter
            @app.route('/<car:re:\w+>/<color:re:#[\da-fA-F]+>')
            def car(req, car, color):
                ...

        If you need to use a group name that is a Python keyword, such as
        'class', you can use the ``**kwargs`` syntax:

        .. code:: python

            @app.route('/<class>/<len:int>')
            def classes(req, **kwargs):
                return ("'%s' class is %d length." %
                        (kwargs['class'], kwargs['len']))

        Be mindful of the ordering when calling this decorator or the set_route
        function with group regular expressions. Regular expression routes are
        checked in the same order as they are created in the internal table.
        The first match stops any further searching. In fact, if groups are
        detected, they will be transferred to normal regular expressions and
        added to a second internal table.
        """

        def wrapper(fun):
            self.set_route(uri, fun, method)
            return fun

        return wrapper

    def set_route(
        self, uri: str, fun: Callable, method: int = METHOD_HEAD | METHOD_GET
    ):
        """Sets a handler for a URI and method.

        Another way to add ``fun`` as a handler for the URI. See
        Application.route documentation for details.

        .. code:: python

            app.set_route('/use/post', user_create, METHOD_POST)
        """
        # Check for invalid spaces in route filter definitions
        if re_invalid_filter.search(uri):
            msg = (
                f"Invalid route definition '{uri}': "
                "Route filter definitions must not contain spaces. "
                "Use '<name:filter>' format without any spaces. "
                "Examples: '<id:int>', '<name:word>', '<value:float>'"
            )
            raise ValueError(msg)

        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + "$"
            converters = tuple(
                (g[0], self.__converter(g[1]))
                for g in (m.groups() for m in re_filter.finditer(uri))
            )
            self.set_regular_route(r_uri, fun, method, converters, uri)
        else:
            if uri not in self.__handlers:
                self.__handlers[uri] = {}
            for val in methods.values():
                if method & val:
                    self.__handlers[uri][val] = fun

    def pop_route(self, uri: str, method: int):
        """Pops a handler for a URI and method from the handlers table.

        The method must be defined uniquely, so METHOD_GET_POST cannot be used.
        If you want to remove a handler for both methods, you must call
        pop_route for each method state.
        """
        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + "$"
            return self.pop_regular_route(r_uri, method)

        handlers = self.__handlers.get(uri, {})
        rval = handlers.pop(method)
        if not handlers:  # is empty
            self.__handlers.pop(uri, None)
        return rval

    def is_route(self, uri: str):
        """Checks if the URI has any registered record."""
        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + "$"
            return self.is_regular_route(r_uri)
        return uri in self.__handlers

    def regular_route(self, ruri: str, method: int = METHOD_HEAD | METHOD_GET):
        r"""Wraps a function to be a handler for a URI defined by a regular
        expression.

        Both regular_route and set_regular_route functions store routes
        in a special internal table, which is separate from the table of static
        routes.

        .. code:: python

            # simple regular expression
            @app.regular_route(r'/user/\w+')
            def any_user(req):
                ...

            # regular expression with named group
            @app.regular_route(r'/user/(?P<user>\w+)')
            def user_detail(req, user):             # named path args
                ...

        Be mindful of the ordering when calling this decorator or the
        set_regular_route function. Regular expression routes are checked
        in the same order as they are created in the internal table. The
        first match stops any further searching.
        """

        def wrapper(fun):
            self.set_regular_route(ruri, fun, method)
            return fun

        return wrapper

    def set_regular_route(
        self,
        uri: str,
        fun: Callable,
        method: int = METHOD_HEAD | METHOD_GET,
        converters=(),
        rule: Optional[str] = None,
    ):
        r"""Sets a handler for a URI defined by a regular expression.

        Another way to add ``fun`` as a handler for a URI defined by a
        regular expression. See Application.regular_route documentation
        for details.


        .. code:: python

            app.set_regular_route('/use/\w+/post', user_create, METHOD_POST)

        This method is used internally when groups are found in a static route,
        added by the route or set_route method.
        """
        r_uri = re.compile(uri, re.U)
        if r_uri not in self.__rhandlers:
            self.__rhandlers[r_uri] = {}
        for val in methods.values():
            if method & val:
                self.__rhandlers[r_uri][val] = (fun, converters, rule)

    def pop_regular_route(self, uri: str, method: int):
        """Pops a handler and converters for a URI and method from the handlers
        table.

        For more details, see Application.pop_route.
        """
        r_uri = re.compile(uri, re.U)
        handlers = self.__rhandlers.get(r_uri, {})
        rval = handlers.pop(method)
        if not handlers:  # is empty
            self.__rhandlers.pop(r_uri, None)
        return rval

    def is_regular_route(self, r_uri):
        """Checks if a regular expression URI has any registered record."""
        r_uri = re.compile(r_uri, re.U)
        return r_uri in self.__rhandlers

    def http_state(
        self,
        status_code: int,
        method: int = METHOD_HEAD | METHOD_GET | METHOD_POST,
    ):
        """Wraps a function to handle HTTP status codes.

        .. code:: python

            @app.http_state(state.HTTP_NOT_FOUND)
            def page_not_found(req, *_):
                return "Your page %s was not found." % req.path, "text/plain"
        """

        def wrapper(fun):
            self.set_http_state(status_code, fun, method)
            return fun

        return wrapper

    def set_http_state(
        self,
        status_code: int,
        fun: Callable,
        method: int = METHOD_HEAD | METHOD_GET | METHOD_POST,
    ):
        """Sets a function as the handler for an HTTP state code and method."""
        if status_code not in self.__shandlers:
            self.__shandlers[status_code] = {}
        for val in methods.values():
            if method & val:
                self.__shandlers[status_code][val] = fun

    def pop_http_state(self, status_code: int, method: int):
        """Pops a handler for an HTTP state and method.

        Similar to Application.pop_route, to pop a multi-method handler, you
        must call pop_http_state for each method.
        """
        handlers = self.__shandlers.get(status_code, {})
        return handlers.pop(method)

    def error_handler(
        self,
        error: Type[Exception],
        method: int = METHOD_HEAD | METHOD_GET | METHOD_POST,
    ):
        """Wraps a function to handle exceptions.

        .. code:: python

            @app.error_handler(ValueError)
            def value_error(req, error):
                log.exception("ValueError %s", error)
                return "Values %s are not correct." % req.args, "text/plain"
        """

        def wrapper(fun):
            self.set_error_handler(error, fun, method)
            return fun

        return wrapper

    def set_error_handler(
        self,
        error: Type[Exception],
        fun: Callable,
        method: int = METHOD_HEAD | METHOD_GET | METHOD_POST,
    ):
        """Sets a function as the handler for an exception and method."""
        if error not in self.__ehandlers:
            self.__ehandlers[error] = {}
        for val in methods.values():
            if method & val:
                self.__ehandlers[error][val] = fun

    def pop_error_handler(self, error: Type[Exception], method: int):
        """Pops a handler for an exception and method.

        Similar to Application.pop_route, to pop a multi-method handler,
        you must call pop_error_handler for each method.
        """
        handlers = self.__ehandlers.get(error, {})
        return handlers.pop(method)

    def state_from_table(self, req: SimpleRequest, status_code: int, **kwargs):
        """Internal method, which is called if another HTTP state has occurred.

        If the status code is in Application.shandlers (filled with the
        http_state function), this handler is called.
        """
        if (
            status_code in self.__shandlers
            and req.method_number in self.__shandlers[status_code]
        ):
            try:
                handler = self.__shandlers[status_code][req.method_number]
                req.error_handler = handler
                return handler(req, **kwargs)
            except HTTPException as http_err:
                response = http_err.make_response()
                if response:
                    return response
                return internal_server_error(req)
            except Exception:  # pylint: disable=broad-except
                return internal_server_error(req)
        elif status_code in default_states:
            handler = default_states[status_code][METHOD_GET]
            req.error_handler = handler
            return handler(req, **kwargs)
        else:
            return not_implemented(req, status_code)

    def error_from_table(self, req: SimpleRequest, error: Exception):
        """Internal method, which is called when an exception is raised."""

        handler = None
        for error_type, hdls in self.__ehandlers.items():
            if isinstance(error, error_type) and req.method_number in hdls:
                handler = hdls[req.method_number]
                break

        if handler:
            try:
                req.error_handler = handler
                return handler(req, error)

            except HTTPException as http_err:
                response = http_err.make_response()
                if response:
                    return response
                status_code = http_err.args[0]
                kwargs = http_err.args[1]
                return to_response(
                    self.state_from_table(req, status_code, **kwargs)
                )

            except Exception:  # pylint: disable=broad-except
                return internal_server_error(req)
        return None

    def handler_from_default(self, req: SimpleRequest):
        """Internal method, which is called if no handler is found."""
        req.uri_rule = "/*"
        if req.method_number in self.__dhandlers:
            req.uri_handler = self.__dhandlers[req.method_number]
            self.handler_from_before(req)  # call before handlers now
            return self.__dhandlers[req.method_number](req)

        self.handler_from_before(req)  # call before handlers now
        log.error("404 Not Found: %s %s", req.method, req.path)
        raise HTTPException(HTTP_NOT_FOUND)

    def handler_from_before(self, req: SimpleRequest):
        """Internal method, which runs all before (pre_process) handlers.

        This method is called before the endpoint route handler.
        """
        for fun in self.__before:
            fun(req)

    def handler_from_table(self, req: Request):  # noqa: C901
        """Calls the correct handler from the handlers table (populated
        by the route function).

        If no handler is found, it attempts to serve a file from Document Root
        or a directory listing if Document Index is also enabled. Then it
        attempts to call the default handler for the correct method or
        calls the handler for status code 404 (Not Found).
        """
        # pylint: disable=too-many-return-statements
        # static routes

        if req.path in self.__handlers:
            if req.method_number in self.__handlers[req.path]:
                handler = self.__handlers[req.path][req.method_number]
                req.uri_rule = req.path  # nice variable for before handlers
                req.uri_handler = handler
                self.handler_from_before(req)  # call before handlers now
                return handler(req)  # call right handler now

            self.handler_from_before(req)  # call before handlers now
            raise HTTPException(HTTP_METHOD_NOT_ALLOWED)

        # regular expression
        for ruri in self.__rhandlers:
            match = ruri.match(req.path)
            if match and req.method_number in self.__rhandlers[ruri]:
                handler, converters, rule = self.__rhandlers[ruri][
                    req.method_number
                ]
                req.uri_rule = rule or ruri.pattern
                req.uri_handler = handler
                if converters:
                    # create OrderedDict from match inside of dict for
                    # converters applying
                    req.path_args = OrderedDict(
                        (g, c(v))
                        for ((g, c), v) in zip(converters, match.groups())
                    )
                    self.handler_from_before(req)  # call before handlers now
                    return handler(req, *req.path_args.values())

                req.path_args = match.groupdict()
                self.handler_from_before(req)  # call before handlers now
                return handler(req, *match.groups())

        # try file or index
        if req.document_root and req.method_number & (
            METHOD_HEAD | METHOD_GET
        ):
            rfile = "%s%s" % (
                req.document_root,
                path.normpath("%s" % req.path),
            )

            if not path.exists(rfile):
                if req.debug and req.path == "/debug-info":  # work if debug
                    req.uri_rule = "/debug-info"
                    req.uri_handler = debug_info
                    self.handler_from_before(req)  # call before handlers now
                    return debug_info(req, self)
                return self.handler_from_default(req)  # try default

            # return file
            if path.isfile(rfile) and access(rfile, R_OK):
                req.uri_rule = "/*"
                self.handler_from_before(req)  # call before handlers now
                log.info("Return file: %s", req.path)
                return FileResponse(rfile)

            # return directory index
            if (
                req.document_index
                and path.isdir(rfile)
                and access(rfile, R_OK)
            ):
                log.info("Return directory: %s", req.path)
                req.uri_rule = "/*"
                req.uri_handler = directory_index
                self.handler_from_before(req)  # call before handlers now
                return directory_index(req, rfile)
            self.handler_from_before(req)  # call before handlers now
            raise HTTPException(HTTP_FORBIDDEN)
        # req.document_root

        if req.debug and req.path == "/debug-info":
            req.uri_rule = "/debug-info"
            req.uri_handler = debug_info
            self.handler_from_before(req)  # call before handlers now
            return debug_info(req, self)

        return self.handler_from_default(req)

    def __request__(self, env, start_response):  # noqa: C901
        """Creates a Request instance and returns a WSGI response.

        This method creates a Request object, calls handlers from
        Application.before, the URI handler (handler_from_table), the
        default handler (Application.defaults) or the error handler
        (Application.state_from_table), and handlers from
        Application.after.
        """
        # pylint: disable=method-hidden,too-many-branches,too-many-statements
        env["REQUEST_STARTTIME"] = time()
        request = None

        try:
            request = Request(env, self)
            args = self.handler_from_table(request)
            response = to_response(args)
        except HTTPException as http_err:
            if request is None:
                request = SimpleRequest(env, self)

            response = http_err.make_response()
            if not response:
                status_code = http_err.args[0]
                kwargs = http_err.args[1]
                response = to_response(
                    self.state_from_table(request, status_code, **kwargs)
                )
        except (ConnectionError, SystemExit) as err:
            log.warning(str(err))
            log.warning("   ***   You should ignore next error   ***")
            return ()
        except ResponseError:
            log.error("Bad returned value from %s", request.uri_handler)
            try:
                response = to_response(self.state_from_table(request, 500))
            except Exception:  # pylint: disable=broad-except
                log.error("Bad returned value from %s", request.error_handler)
                response = internal_server_error(request)

        except BaseException as err:  # pylint: disable=broad-except
            if request is None:
                log.critical(str(err), exc_info=True)
                request = SimpleRequest(env, self)
            try:
                response = self.error_from_table(request, err)
                if not response:
                    response = to_response(self.state_from_table(request, 500))
            except Exception:  # pylint: disable=broad-except
                log.error("Bad returned value from %s", request.error_handler)
                response = internal_server_error(request)

        __fn = None
        try:  # call post_process handler
            for fun in self.__after:
                __fn = fun
                response = to_response(fun(request, response))
        except BaseException as err:  # pylint: disable=broad-except
            log.error(
                "Handler %s from %s returns invalid data or crashed",
                __fn,
                __fn.__module__,
            )
            response = self.error_from_table(request, err)
            if not response:
                response = to_response(self.state_from_table(request, 500))

        skip_sendfile = request.server_software == "uWsgi" and response.ranges
        # need working fileno method
        try:
            if (
                isinstance(response, FileObjResponse)
                and "wsgi.file_wrapper" in env
                and not skip_sendfile
            ):
                return env["wsgi.file_wrapper"](response(start_response))
            return response(start_response)  # return bytes generator
        except HTTPException as http_err:  # HTTP_RANGE_NOT_SATISFIABLE case
            response = http_err.make_response()
            return response(start_response)

    def __call__(self, env, start_response):
        """Callable defined for the Application instance.

        This method runs the __request__ method.
        """
        return self.__request__(env, start_response)

    def __profile_request__(self, env, start_response):
        """Profiler version of __request__.

        This method is used if set_profile is called.
        """

        # pylint: disable=possibly-unused-variable
        def wrapper(rval):
            rval.append(self.__original_request__(env, start_response))

        rval = []
        uri_dump = (
            self.__dump
            + "_"
            + env.get("REQUEST_METHOD")
            + env.get("PATH_INFO").replace("/", "_")
            + "."
            + str(time())
            + ".profile"
        )
        log.info("Generate %s", uri_dump)
        self.__runctx("wrapper(rval)", globals(), locals(), filename=uri_dump)
        return rval[0]

    def __repr__(self):
        return "%s - callable Application class instance" % self.__name

    def set_profile(self, runctx, dump):
        """Sets a profiler for the __call__ function.

        runctx
            Function from the profiler module.
        dump
            Path and prefix for .profile files.

        Typical usage:

        .. code:: python

            import cProfile

            cProfile.runctx('from simple import *', globals(), locals(),
                            filename="log/init.profile")
            app.set_profile(cProfile.runctx, 'log/req')
        """
        self.__runctx = runctx
        self.__dump = dump

        self.__original_request__ = self.__request__
        self.__request__ = self.__profile_request__

    def del_profile(self):
        """Removes the profiler from the application."""
        self.__request__ = self.__original_request__

    @staticmethod
    def get_options():
        """Returns a dictionary with application variables from the system
        environment.

        Application variables start with the ``app_`` prefix,
        but in the returned dictionary, they are set without this prefix.

        .. code:: python

            app_db_server = localhost   # application variable db_server
            app_templates = app/templ   # application variable templates

        This method works like Request.get_options, but it works with
        os.environ, so it is effective only with WSGI servers that set
        not only the request environment, but also os.environ. Apache's
        mod_wsgi does not do that; uWsgi and PoorHTTP do.
        """
        options = {}
        for key, val in environ.items():
            key = key.strip()
            if key[:4].lower() == "app_":
                options[key[4:].lower()] = val.strip()
        return options
