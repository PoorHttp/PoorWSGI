"""Application callable class, which is the main point for wsgi application.

:Classes:   Application
:Functions: to_response

"""
# pylint: disable=too-many-lines
# pylint: disable=unsubscriptable-object

from os import path, access, R_OK, environ
from collections import OrderedDict, namedtuple
from logging import getLogger
from hashlib import md5, sha256
from typing import List, Union, Callable, Optional

import re

from poorwsgi.state import HTTP_OK, DECLINED, \
    METHOD_GET, METHOD_POST, METHOD_HEAD, methods, \
    HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, HTTP_FORBIDDEN
from poorwsgi.request import Request
from poorwsgi.results import default_states, not_implemented, \
    internal_server_error, directory_index, debug_info
from poorwsgi.response import Response, HTTPException, EmptyResponse, \
    FileResponse, make_response, ResponseError

log = getLogger("poorwsgi")

# check, if there is define filter in uri
re_filter = re.compile(r'<(\w+)(:[^>]+)?>')

# Supported authorization algorithms
AUTH_DIGEST_ALGORITHMS = {
    'MD5': md5,
    'MD5-sess': md5,
    'SHA-256': sha256,
    'SHA-256-sess': sha256,
    # 'SHA-512-256': sha512,  # Need extend library
    # 'SHA-512-256-sess': sha512,
}


def to_response(response):
    """handler response to application response."""
    if isinstance(response, Response):
        return response

    if not isinstance(response, tuple):
        response = (response,)
    return make_response(*response)


class Application():
    """Poor WSGI application which is called by WSGI server.

    Working of is describe in PEP 0333. This object store route dispatch table,
    and have methods for it's using and of course __call__ method for use
    as WSGI application.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods
    __instances: List[str] = []

    def __init__(self, name="__main__"):
        """Application class is per name singleton.

        That means, there could be exist only one instance with same name.
        """
        if Application.__instances.count(name):
            raise RuntimeError('Application with name %s exist yet.' % name)
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
            ':int': (r'-?\d+', int),
            ':float': (r'-?\d+(\.\d+)?', float),
            ':word': (r'\w+', str),
            ':hex': (r'[0-9a-fA-F]+', str),
            ':re:': (None, str),
            'none': (r'[^/]+', str)
        }

        # handlers of regex paths: {r'/user/([a-z]?)': {METHOD_GET: handler}}
        self.__rhandlers = OrderedDict()

        # http state handlers: {HTTP_NOT_FOUND: {METHOD_GET: my_404_handler}}
        self.__shandlers = {}

        # -- Application variable
        self.__config = {
            'auto_args': True,
            'auto_form': True,
            'auto_json': True,
            'auto_data': True,
            'data_size': 32768,
            'keep_blank_values': 0,
            'strict_parsing': 0,
            'file_callback': None,
            'json_mime_types': [
                'application/json',
                'application/javascript',
                'application/merge-patch+json'],
            'form_mime_types': [
                'application/x-www-form-urlencoded',
                'multipart/form-data'
            ],
            'auto_cookies': True,
            'debug': 'Off',
            'document_root': '',
            'document_index': 'Off',
            'secret_key': None,
            'auth_type': None,
            'auth_algorithm': 'MD5-sess',
            'auth_qop': 'auth',
            'auth_timeout': 300,
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
        elif _filter[:4] == ':re:':     # :re: filter have user defined regex
            regex = _filter[4:]
        else:
            try:
                regex = self.__filters[_filter][0]
            except KeyError as err:
                raise RuntimeError("Undefined route group filter '%s'" %
                                   _filter) from err

        return "(?P<%s>%s)" % (groups[0], regex)

    def __convertor(self, _filter):
        _filter = str(_filter).lower()
        _filter = ':re:' if _filter[:4] == ':re:' else _filter
        try:
            return self.__filters[_filter][1]
        except KeyError as err:
            raise RuntimeError("Undefined route group filter '%s'" %
                               _filter) from err

    @property
    def name(self):
        """Return application name."""
        return self.__name

    @property
    def filters(self):
        """Copy of filter table.

        Filter table contains regular expressions and convert functions,
        see Application.set_filter and Application.route.

        Default filters are:

            **:int**    match number and convert it to int

            **:float**  match number and convert it to float

            **:word**   match one string word

            **:hex**    match hexadecimal value and convert it to str

            **:re:**    match user defined regular expression

            **none**    match any string without '/' character

        For more details see `/debug-info` page of your application, where
        you see all filters with regular expression definition.
        """
        return self.__filters.copy()

    @property
    def before(self):
        """Tuple of table with before-request handlers.

        See Application.before_request.
        """
        return tuple(self.__before)

    @property
    def after(self):
        """Tuple of table with after-request handlers.

        See Application.after_request.
        """
        return tuple(self.__after)

    @property
    def defaults(self):
        """Copy of table with default handlers.

        See Application.set_default
        """
        return self.__dhandlers.copy()

    @property
    def routes(self):
        """Copy of table with static handlers.

        See Application.route.
        """
        return self.__handlers.copy()

    @property
    def regular_routes(self):
        """Copy of table with regular expression handlers.

        See Application.route and Application.regular_route.
        """
        return self.__rhandlers.copy()

    @property
    def states(self):
        """Copy of table with http state aka error handlers.

        See Application.http_state
        """
        return self.__shandlers.copy()

    @property
    def auto_args(self):
        """Automatic parsing request arguments from uri.

        If it is True (default), Request object do automatic parsing request
        uri to its args variable.
        """
        return self.__config['auto_args']

    @auto_args.setter
    def auto_args(self, value):
        self.__config['auto_args'] = bool(value)

    @property
    def auto_form(self):
        """Automatic parsing arguments from request body.

        If it is True (default) and method is POST, PUT or PATCH, and
        request mime type is one of form_mime_types, Request
        object do automatic parsing request body to its form variable.
        """
        return self.__config['auto_form']

    @auto_form.setter
    def auto_form(self, value):
        self.__config['auto_form'] = bool(value)

    @property
    def auto_json(self):
        """Automatic parsing JSON from request body.

        If it is True (default), method is POST, PUT or PATCH and request
        mime type is one of json_mime_types, Request object do
        automatic parsing request body to json variable.
        """
        return self.__config['auto_json']

    @auto_json.setter
    def auto_json(self, value):
        self.__config['auto_json'] = bool(value)

    @property
    def auto_data(self):
        """Enabling Request.data property for smaller requests.

        Default value is True.
        """
        return self.__config['auto_data']

    @auto_data.setter
    def auto_data(self, value: Union[int, bool]):
        self.__config['auto_data'] = bool(value)

    @property
    def data_size(self):
        """Size limit for Request.data property.

        This value is  which is compare to request Content-Type. Default value
        is 32768 as 30Kb.
        """
        return self.__config['data_size']

    @data_size.setter
    def data_size(self, value: int):
        self.__config['data_size'] = int(value)

    @property
    def auto_cookies(self):
        """Automatic parsing cookies from request headers.

        If it is True (default) and Cookie request header was set,
        SimpleCookie object was paresed to Request property cookies.
        """
        return self.__config['auto_cookies']

    @auto_cookies.setter
    def auto_cookies(self, value: Union[int, bool]):
        self.__config['auto_cookies'] = bool(value)

    @property
    def debug(self):
        """Application debug as another way how to set poor_Debug.

        This setting will be rewrite by poor_Debug environment variable.
        """
        return self.__config['debug'] == 'On'

    @debug.setter
    def debug(self, value: Union[int, bool]):
        self.__config['debug'] = 'On' if bool(value) else 'Off'

    @property
    def document_root(self):
        """Application document_root as another way how to set poor_DocumentRoot.

        This setting will be rewrite by poor_DocumentRoot environ variable.
        """
        return self.__config['document_root']

    @document_root.setter
    def document_root(self, value: str):
        self.__config['document_root'] = value

    @property
    def document_index(self):
        """Application document_root as another way how to set poor_DocumentRoot.

        This setting will be rewrite by poor_DocumentRoot environ variable.
        """
        return self.__config['document_index'] == 'On'

    @document_index.setter
    def document_index(self, value: Union[int, bool]):
        self.__config['document_index'] = 'On' if bool(value) else 'Off'

    @property
    def secret_key(self):
        """Application secret_key could be replace by poor_SecretKey in request.

        Secret key is used by PoorSession class. It is generate from
        some server variables, and the best way is set to your own long
        key."""
        return self.__config['secret_key']

    @secret_key.setter
    def secret_key(self, value: str):
        self.__config['secret_key'] = value

    @property
    def keep_blank_values(self):
        """Keep blank values in request arguments.

        If it is 1 (0 is default), automatic parsing request uri or body
        keep blank values as empty string.
        """
        return self.__config['keep_blank_values']

    @keep_blank_values.setter
    def keep_blank_values(self, value: Union[int, bool]):
        self.__config['keep_blank_values'] = int(value)

    @property
    def strict_parsing(self):
        """Strict parse request arguments.

        If it is 1 (0 is default), automatic parsing request uri or body
        raise with exception on parsing error.
        """
        return self.__config['strict_parsing']

    @strict_parsing.setter
    def strict_parsing(self, value: Union[int, bool]):
        self.__config['strict_parsing'] = int(value)

    @property
    def file_callback(self):
        """File callback use as parameter when parsing request body.

        Default is None. Values could be a class or factory which got's
        filename from request body and have file compatibile interface.
        """
        return self.__config['file_callback']

    @file_callback.setter
    def file_callback(self, value: Callable):
        self.__config['file_callback'] = value

    @property
    def json_mime_types(self):
        """Copy of json mime type list.

        Containt list of strings as json mime types, which is use for
        testing, when automatics Json object is create from request body.
        """
        return self.__config['json_mime_types']

    @property
    def auth_type(self):
        """Authorization type.

        Only ``Digest`` type is supported now.
        """
        return self.__config['auth_type']

    @auth_type.setter
    def auth_type(self, value: str):
        value = value.capitalize()
        if value not in ('Digest',):
            raise ValueError('Unsupported authorization type')
        # for Digest
        if self.__config['secret_key'] is None:
            raise ValueError('Set secret key first')
        self.__config['auth_type'] = value

    @property
    def auth_algorithm(self):
        """Authorization algorithm.

        Algorithm depends on authorization type and client support.
        Supported:

        :Digest: MD5 | MD5-sess | SHA256 | SHA256-sess
        :default: MD5-sess
        """
        return self.__config['auth_algorithm']

    @auth_algorithm.setter
    def auth_algorithm(self, value: str):
        if self.__config['auth_algorithm'] is None:
            raise ValueError('Set authorization type first')

        if self.__config['auth_algorithm'] == 'Digest':
            if value not in AUTH_DIGEST_ALGORITHMS:
                raise ValueError('Unsupported Digest algorithm')
        self.__config['auth_algorithm'] = value
        self.__auth_hash = AUTH_DIGEST_ALGORITHMS[value]

    @property
    def auth_hash(self):
        """Return authorization hash function.

        Function can be changed by auth_algorithm property.

        :default: md5
        """
        return self.__auth_hash

    @property
    def auth_qop(self):
        """Authorization quality of protection.

        This is use for Digest authorization only. When browsers
        supports only ``auth`` or empty value, PoorWSGI supports the same.

        :default: auth
        """
        return self.__config['auth_qop']

    @auth_qop.setter
    def auth_qop(self, value: str):
        if value not in ('', 'auth', None):
            raise ValueError('Unsupported quality of protection')
        self.__config['auth_qop'] = value

    @property
    def auth_timeout(self):
        """Digest Authorization timeout of nonce value in seconds.

        In fact, timeout will be between timeout and 2*timeout, because
        time alignment is used. If timeout is None or 0, no timeout is used.

        :default: 300 (5min)
        """
        return self.__config['auth_timeout']

    @auth_timeout.setter
    def auth_timeout(self, value: Optional[int]):
        if not isinstance(value, (type(None), int)):
            raise ValueError('Unsupported auth_timeout value')
        self.__config['auth_timeout'] = value

    @property
    def form_mime_types(self):
        """Copy of form mime type list.

        Containt list of strings as form mime types, which is use for
        testing, when automatics Form object is create from request body.
        """
        return self.__config['form_mime_types']

    def set_filter(self, name: str, regex: str, convertor: Callable = str):
        r"""Create new filter or overwrite builtins.

        name : str
            Name of filter which is used in route or set_route method.
        regex : str
            Regular expression which used for filter.
        convertor : function
            Convertor function or class, which gets string in input. Default is
            str function, which call __str__ method on input object.

        .. code:: python

            app.set_filter('uint', r'\d+', int)
        """
        name = ':'+name if name[0] != ':' else name
        self.__filters[name] = (regex, convertor)

    def before_request(self):
        """Append hendler to call before each request.

        This is decorator for function to call before each request.

        .. code:: python

            @app.before_request()
            def before_each_request(req):
                print("Request coming")
        """
        def wrapper(fun):
            self.add_before_request(fun)
            return fun
        return wrapper

    def add_before_request(self, fun: Callable):
        """Append handler to call before each request.

        Method adds function to list functions which is call before each
        request.

        .. code:: python

            def before_each_request(req):
                print("Request coming")

            app.add_before(before_each_request)
        """
        if self.__before.count(fun):
            raise ValueError("%s is in list yet" % str(fun))
        self.__before.append(fun)

    def pop_before_request(self, fun: Callable):
        """Remove handler added by add_before_request or before_request."""
        if not self.__before.count(fun):
            raise ValueError("%s is not in list" % str(fun))
        self.__before.remove(fun)

    def after_request(self):
        """Append handler to call after each request.

        This decorator append function to be called after each request,
        if you want to use it redefined all outputs.

        .. code:: python

            @app.after_each_request()
            def after_each_request(request, response):
                print("Request out")
                return response
        """
        def wrapper(fun):
            self.add_after_request(fun)
            return fun
        return wrapper

    def add_after_request(self, fun: Callable):
        """Append handler to call after each request.

        Method for direct append function to list functions which are called
        after each request.

        .. code:: python

            def after_each_request(request, response):
                print("Request out")
                return response

            app.add_after_request(after_each_request)
        """
        if self.__after.count(fun):
            raise ValueError("%s is in list yet" % str(fun))
        self.__after.append(fun)

    def pop_after_request(self, fun: Callable):
        """Remove handler added by add_before_request or before_request."""
        if not self.__before.count(fun):
            raise ValueError("%s is not in list" % str(fun))
        self.__after.remove(fun)

    def default(self, method: int = METHOD_HEAD | METHOD_GET):
        """Set default handler.

        This is decorator for default handler for http method (called before
        error_not_found).

        .. code:: python

            @app.default(METHOD_GET_POST)
            def default_get_post(req):
                # this function will be called if no uri match in internal
                # uri table with method. It's similar like not_found error,
                # but without error
                ...
        """
        def wrapper(fun):
            self.set_default(fun, method)
            return fun
        return wrapper
    # enddef

    def set_default(self, fun: Callable,
                    method: int = METHOD_HEAD | METHOD_GET):
        """Set default handler.

        Set fun default handler for http method called befor error_not_found.

        .. code:: python

            app.set_default(default_get_post, METHOD_GET_POST)
        """
        for val in methods.values():
            if method & val:
                self.__dhandlers[val] = fun
    # enddef

    def pop_default(self, method: int):
        """Pop default handler for method."""
        return self.__dhandlers.pop(method)

    def route(self, uri: str, method: int = METHOD_HEAD | METHOD_GET):
        r"""Wrap function to be handler for uri and specified method.

        You can define uri as static path or as groups which are hand
        to handler as next parameters.

        .. code:: python

            # static uri
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

            # group with own regular expression filter
            @app.route('/<car:re:\w+>/<color:re:#[\da-fA-F]+>')
            def car(req, car, color):
                ...

        If you can use some name of group which is python keyword, like class,
        you can use \**kwargs syntax:

        .. code:: python

            @app.route('/<class>/<len:int>')
            def classes(req, **kwargs):
                return ("'%s' class is %d lenght." %
                        (kwargs['class'], kwargs['len']))

        Be sure with ordering of call this decorator or set_route function with
        groups regular expression. Regular expression routes are check with the
        same ordering, as you create internal table of them. First match stops
        any other searching. In fact, if groups are detect, they will be
        transfer to normal regular expression, and will be add to second
        internal table.
        """
        def wrapper(fun):
            self.set_route(uri, fun, method)
            return fun
        return wrapper
    # enddef

    def set_route(self, uri: str, fun: Callable,
                  method: int = METHOD_HEAD | METHOD_GET):
        """Set handler for uri and method.

        Another way to add fun as handler for uri. See Application.route
        documentation for details.

        .. code:: python

            app.set_route('/use/post', user_create, METHOD_POST)
        """
        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            convertors = tuple((g[0], self.__convertor(g[1]))
                               for g in (m.groups()
                                         for m in re_filter.finditer(uri)))
            self.set_regular_route(r_uri, fun, method, convertors, uri)
        else:
            if uri not in self.__handlers:
                self.__handlers[uri] = {}
            for val in methods.values():
                if method & val:
                    self.__handlers[uri][val] = fun

    def pop_route(self, uri: str, method: int):
        """Pop handler for uri and method from handers table.

        Method must be define unique, so METHOD_GET_POST could not be use.
        If you want to remove handler for both methods, you must call pop route
        for each method state.
        """
        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            return self.pop_regular_route(r_uri, method)

        handlers = self.__handlers.get(uri, {})
        rval = handlers.pop(method)
        if not handlers:    # is empty
            self.__handlers.pop(uri, None)
        return rval

    def is_route(self, uri: str):
        """Check if uri have any registered record."""
        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            return self.is_regular_route(r_uri)
        return uri in self.__handlers

    def regular_route(self, ruri: str, method: int = METHOD_HEAD | METHOD_GET):
        r"""Wrap function to be handler for uri defined by regular expression.

        Both of function, regular_route and set_regular_route store routes
        to special internal table, which is another to table of static routes.

        .. code:: python

            # simple regular expression
            @app.regular_route(r'/user/\w+')
            def any_user(req):
                ...

            # regular expression with
            @app.regular_route(r'/user/(?P<user>\w+)')
            def user_detail(req, user):             # named path args
                ...

        Be sure with ordering of call this decorator or set_regular_route
        function. Regular expression routes are check with the same ordering,
        as you create internal table of them. First match stops any other
        searching.
        """
        def wrapper(fun):
            self.set_regular_route(ruri, fun, method)
            return fun
        return wrapper

    def set_regular_route(self, uri: str, fun: Callable,
                          method: int = METHOD_HEAD | METHOD_GET,
                          convertors=(), rule: str = None):
        r"""Set hanlder for uri defined by regular expression.

        Another way to add fn as handler for uri defined by regular expression.
        See Application.regular_route documentation for details.


        .. code:: python

            app.set_regular_route('/use/\w+/post', user_create, METHOD_POST)

        This method is internally use, when groups are found in static route,
        adding by route or set_route method.
        """
        # pylint: disable=too-many-arguments
        r_uri = re.compile(uri, re.U)
        if r_uri not in self.__rhandlers:
            self.__rhandlers[r_uri] = {}
        for val in methods.values():
            if method & val:
                self.__rhandlers[r_uri][val] = (fun, convertors, rule)

    def pop_regular_route(self, uri: str, method: int):
        """Pop handler and convertors for uri and method from handlers table.

        For mor details see Application.pop_route.
        """
        r_uri = re.compile(uri, re.U)
        handlers = self.__rhandlers.get(r_uri, {})
        rval = handlers.pop(method)
        if not handlers:    # is empty
            self.__rhandlers.pop(r_uri, None)
        return rval

    def is_regular_route(self, r_uri):
        """Check if regular expression uri have any registered record."""
        r_uri = re.compile(r_uri, re.U)
        return r_uri in self.__rhandlers

    def http_state(self, status_code: int,
                   method: int = METHOD_HEAD | METHOD_GET | METHOD_POST):
        """Wrap function to handle http status codes like http errors.

        .. code:: python

            @app.http_state(state.HTTP_NOT_FOUND)
            def page_not_found(req):
                return "Your request %s not found." % req.uri, "text/plain"
        """
        def wrapper(fun):
            self.set_http_state(status_code, fun, method)
            return fun
        return wrapper

    def set_http_state(self, status_code: int, fun: Callable,
                       method: int = METHOD_HEAD | METHOD_GET | METHOD_POST):
        """Set fn as handler for http state code and method."""
        if status_code not in self.__shandlers:
            self.__shandlers[status_code] = {}
        for val in methods.values():
            if method & val:
                self.__shandlers[status_code][val] = fun

    def pop_http_state(self, status_code, method: int):
        """Pop handerl for http state and method.

        As Application.pop_route, for pop multimethod handler, you must call
        pop_http_state for each method.
        """
        handlers = self.__shandlers.get(status_code, {})
        return handlers.pop(method)

    def error_from_table(self, req, status_code, **kwargs):
        """Internal method, which is called if error was accured.

        If status code is in Application.shandlers (fill with http_state
        function), call this handler.
        """
        if status_code in self.__shandlers \
                and req.method_number in self.__shandlers[status_code]:
            try:
                handler = self.__shandlers[status_code][req.method_number]
                req.error_handler = handler
                self.handler_from_before(req)  # call before handlers now
                return handler(req, **kwargs)
            except Exception:  # pylint: disable=broad-except
                return internal_server_error(req)
        elif status_code in default_states:
            handler = default_states[status_code][METHOD_GET]
            req.error_handler = handler
            return handler(req, **kwargs)
        else:
            return not_implemented(req, status_code)

    def handler_from_default(self, req):
        """Internal method, which is called if no handler is found."""
        req.uri_rule = '/*'
        if req.method_number in self.__dhandlers:
            req.uri_handler = self.__dhandlers[req.method_number]
            self.handler_from_before(req)       # call before handlers now
            return self.__dhandlers[req.method_number](req)

        self.handler_from_before(req)       # call before handlers now
        log.error("404 Not Found: %s %s", req.method, req.uri)
        raise HTTPException(HTTP_NOT_FOUND)

    def handler_from_before(self, req):
        """Internal method, which run all before (pre_proccess) handlers.

        This method was call before end-point route handler.
        """
        for fun in self.__before:
            fun(req)

    def handler_from_table(self, req):
        """Call right handler from handlers table (fill with route function).

        If no handler is fined, try to find directory or file if Document Root,
        resp. Document Index is set. Then try to call default handler for right
        method or call handler for status code 404 - not found.
        """
        # pylint: disable=too-many-return-statements
        # static routes
        if req.uri in self.__handlers:
            if req.method_number in self.__handlers[req.uri]:
                handler = self.__handlers[req.uri][req.method_number]
                req.uri_rule = req.uri      # nice variable for before handlers
                req.uri_handler = handler
                self.handler_from_before(req)  # call before handlers now
                return handler(req)       # call right handler now

            self.handler_from_before(req)  # call before handlers now
            raise HTTPException(HTTP_METHOD_NOT_ALLOWED)

        # regular expression
        for ruri in self.__rhandlers.keys():
            match = ruri.match(req.uri)
            if match and req.method_number in self.__rhandlers[ruri]:
                handler, convertors, rule = \
                    self.__rhandlers[ruri][req.method_number]
                req.uri_rule = rule or ruri.pattern
                req.uri_handler = handler
                if convertors:
                    # create OrderedDict from match insead of dict for
                    # convertors applying
                    req.path_args = OrderedDict(
                        (g, c(v))for ((g, c), v) in zip(convertors,
                                                        match.groups()))
                    self.handler_from_before(req)   # call before handlers now
                    return handler(req, *req.path_args.values())

                req.path_args = match.groupdict()
                self.handler_from_before(req)   # call before handlers now
                return handler(req, *match.groups())

        # try file or index
        if req.document_root and \
                req.method_number & (METHOD_HEAD | METHOD_GET):
            rfile = "%s%s" % (req.document_root,
                              path.normpath("%s" % req.uri))

            if not path.exists(rfile):
                if req.debug and req.uri == '/debug-info':      # work if debug
                    req.uri_rule = '/debug-info'
                    req.uri_handler = debug_info
                    self.handler_from_before(req)  # call before handlers now
                    return debug_info(req, self)
                return self.handler_from_default(req)         # try default

            # return file
            if path.isfile(rfile) and access(rfile, R_OK):
                req.uri_rule = '/*'
                self.handler_from_before(req)      # call before handlers now
                log.info("Return file: %s", req.uri)
                return FileResponse(rfile)

            # return directory index
            if req.document_index and path.isdir(rfile) \
                    and access(rfile, R_OK):
                log.info("Return directory: %s", req.uri)
                req.uri_rule = '/*'
                req.uri_handler = directory_index
                self.handler_from_before(req)      # call before handlers now
                return directory_index(req, rfile)
            self.handler_from_before(req)      # call before handlers now
            raise HTTPException(HTTP_FORBIDDEN)
        # req.document_root

        if req.debug and req.uri == '/debug-info':
            req.uri_rule = '/debug-info'
            req.uri_handler = debug_info
            self.handler_from_before(req)          # call before handlers now
            return debug_info(req, self)

        return self.handler_from_default(req)

    def __request__(self, env, start_response):
        """Create Request instance and return wsgi response.

        This method create Request object, call handlers from
        Application.before, uri handler (handler_from_table), default handler
        (Application.defaults) or error handler (Application.error_from_table),
        and handlers from Application.after.
        """
        # pylint: disable=method-hidden,too-many-branches
        request = None

        try:
            request = Request(env, self)
            args = self.handler_from_table(request)
            response = to_response(args)
        except HTTPException as http_err:
            if isinstance(http_err.args[0], Response):
                response = http_err.args[0]
            else:
                status_code = http_err.args[0]
                kwargs = http_err.args[1]
                if status_code == DECLINED:
                    return ()   # decline the connection
                if status_code == HTTP_OK:
                    response = EmptyResponse()
                else:
                    response = to_response(
                        self.error_from_table(request, status_code, **kwargs))
        except (ConnectionError, SystemExit) as err:
            log.warning(str(err))
            log.warning('   ***   You should ignore next error   ***')
            return ()
        except ResponseError:
            log.error("Bad returned value from %s", request.uri_handler)
            try:
                response = to_response(self.error_from_table(request, 500))
            except Exception:  # pylint: disable=broad-except
                log.error("Bad returned value from %s", request.error_handler)
                response = internal_server_error(request)

        except BaseException as err:  # pylint: disable=broad-except
            if request is None:
                log.critical(str(err))
                Failed = namedtuple(
                    "Failed", ('debug', 'server_software', 'server_admin',
                               'error_handler'))
                request = Failed(
                    self.debug,
                    env.get('SERVER_SOFTWARE', 'Unknown'),
                    env.get('SERVER_ADMIN', 'Unknown'),
                    internal_server_error)

            try:
                response = to_response(self.error_from_table(request, 500))
            except Exception:  # pylint: disable=broad-except
                log.error("Bad returned value from %s", request.error_handler)
                response = internal_server_error(request)

        __fn = None
        try:    # call post_process handler
            for fun in self.__after:
                __fn = fun
                response = to_response(fun(request, response))
        except BaseException:  # pylint: disable=broad-except
            log.error("Handler %s from %s returns invalid data or crashed",
                      __fn, __fn.__module__)
            response = to_response(self.error_from_table(request, 500))

        if isinstance(response, FileResponse) and \
                "wsgi.file_wrapper" in env:     # need working fileno method
            return env['wsgi.file_wrapper'](response(start_response))
        return response(start_response)         # return bytes generator
    # enddef

    def __call__(self, env, start_response):
        """Callable define for Application instance.

        This method run __request__ method.
        """
        return self.__request__(env, start_response)

    def __profile_request__(self, env, start_response):
        """Profiler version of __request__.

        This method is used if set_profile is used."""
        # pylint: disable=possibly-unused-variable
        def wrapper(rval):
            rval.append(self.__original_request__(env, start_response))

        rval = []
        uri_dump = (self.__dump + env.get('PATH_INFO').replace('/', '_') +
                    '.profile')
        log.info('Generate %s', uri_dump)
        self.__runctx('wrapper(rv)', globals(), locals(), filename=uri_dump)
        return rval[0]
    # enddef

    def __repr__(self):
        return '%s - callable Application class instance' % self.__name

    def set_profile(self, runctx, dump):
        """Set profiler for __call__ function.

        runctx : function
            function from profiler module
        dump : str
            path and prefix for .profile files

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
    # enddef

    def del_profile(self):
        """Remove profiler from application."""
        self.__request__ = self.__original_request__

    @staticmethod
    def get_options():
        """Returns dictionary with application variables from system environment.

        Application variables start with ``app_`` prefix,
        but in returned dictionary is set without this prefix.

        .. code:: python

            app_db_server = localhost   # application variable db_server
            app_templates = app/templ   # application variable templates

        This method works like Request.get_options, but work with
        os.environ, so it works only with wsgi servers, which set not only
        request environ, but os.environ too. Apaches mod_wsgi don't do that,
        uWsgi and PoorHTTP do that.
        """
        options = {}
        for key, val in environ.items():
            key = key.strip()
            if key[:4].lower() == 'app_':
                options[key[4:].lower()] = val.strip()
        return options
