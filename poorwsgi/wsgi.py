"""Application callable class, which is the main point for poorwsgi web
application.
"""

from os import path, access, R_OK, environ, getcwd, uname
from sys import version_info, stderr, version

import re

from poorwsgi.state import OK, DONE, DECLINED, HTTP_OK, \
    METHOD_GET, METHOD_POST, METHOD_HEAD, methods, levels, \
    LOG_DEBUG, LOG_INFO, LOG_ERR, LOG_WARNING, \
    HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, HTTP_FORBIDDEN, \
    __version__
from poorwsgi.request import Request, BrokenClientConnection
from poorwsgi.results import default_shandlers, not_implemented, \
    internal_server_error, \
    SERVER_RETURN, send_file, directory_index, debug_info, \
    _unicode_exist, uni

if version_info[0] == 2 and version_info[1] < 7:
    from ordereddict import OrderedDict
else:
    from collections import OrderedDict

# check, if there is define filter in uri
re_filter = re.compile(r'<(\w+)(:[^>]+)?>')


class Application(object):
    """Poor WSGI application which is called by WSGI server.

    Working of is describe in PEP 0333. This object store route dispatch table,
    and have methods for it's using and of course __call__ method for use
    as WSGI application.
    """

    __instances = []

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
        self.__pre = []
        self.__post = []

        # dhandlers table for default handers on methods {METHOD_GET: handler}
        self.__dhandlers = {}

        # handlers table of simple paths: {'/path': {METHOD_GET: handler}}
        self.__handlers = {}

        self.__filters = {
            ':int': (r'-?\d+', int),
            ':float': (r'-?\d+(\.\d+)?', float),
            ':word': (r'\w+', uni),
            ':hex': (r'[0-9a-fA-F]+', str),
            ':re:': (None, uni),
            'none': (r'[^/]+', uni)
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
            'keep_blank_values': 0,
            'strict_parsing': 0,
            'json_content_types': [
                'application/json',
                'application/javascript',
                'application/merge-patch+json'],
            'form_content_types': [
                'application/x-www-form-urlencoded',
                'multipart/form-data'
            ],
            'auto_cookies': True,
            'debug': 'Off',
            'document_root': '',
            'document_index': 'Off',
            'secret_key': '%s%s%s%s' %
                          (__version__, version, getcwd(),
                           ''.join(str(x) for x in uname()))
        }

        try:
            self.__log_level = levels[environ.get('poor_LogLevel',
                                                  'warn').lower()]
        except:
            self.__log_level = LOG_WARNING
            self.log_error('Bad poor_LogLevel, default is warn.', LOG_WARNING)
        # endtry
    # enddef

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
            except KeyError:
                raise RuntimeError("Undefined route group filter '%s'" %
                                   _filter)

        return "(?P<%s>%s)" % (groups[0], regex)
    # enddef

    def __convertor(self, _filter):
        _filter = str(_filter).lower()
        _filter = ':re:' if _filter[:4] == ':re:' else _filter
        try:
            return self.__filters[_filter][1]
        except KeyError:
            raise RuntimeError("Undefined route group filter '%s'" % _filter)

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
            :int - match number and convert it to int
            :float - match number and convert it to float
            :word - match one unicoee word
            :hex - match hexadecimal value and convert it to str
            :re: - match user defined regular expression
            none - match any string withount '/' character

        For more details see {/debug-info} page of your application, where
        you see all filters with regular expression definition.
        """
        return self.__filters.copy()

    @property
    def pre(self):
        """Tuple of table with pre-process handlers.

        See Application.pre_process.
        """
        return tuple(self.__pre)

    @property
    def post(self):
        """Tuple of table with post-process handlers.

        See Application.post_process.
        """
        return tuple(self.__post)

    @property
    def dhandlers(self):
        """Copy of table with default handlers.

        See Application.set_default
        """
        return self.__dhandlers.copy()

    @property
    def handlers(self):
        """Copy of table with static handlers.

        See Application.route.
        """
        return self.__handlers.copy()

    @property
    def rhandlers(self):
        """Copy of table with regular expression handlers.

        See Application.route and Application.rroute.
        """
        return self.__rhandlers.copy()

    @property
    def shandlers(self):
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
        request content type is one of form_content_types, Request
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
        content type is one of json_content_types, Request object do
        automatic parsing request body to json variable.
        """
        return self.__config['auto_json']

    @auto_json.setter
    def auto_json(self, value):
        self.__config['auto_json'] = bool(value)

    @property
    def auto_cookies(self):
        """Automatic parsing cookies from request headers.

        If it is True (default) and Cookie request header was set,
        SimpleCookie object was paresed to Request property cookies.
        """
        return self.__config['auto_cookies']

    @auto_cookies.setter
    def auto_cookies(self, value):
        self.__config['auto_cookies'] = bool(value)

    @property
    def debug(self):
        """Application debug as another way how to set poor_Debug.

        This setting will be rewrite by poor_Debug environment variable.
        """
        return self.__config['debug'] == 'On'

    @debug.setter
    def debug(self, value):
        self.__config['debug'] = 'On' if bool(value) else 'Off'

    @property
    def document_root(self):
        """Application document_root as another way how to set poor_DocumentRoot.

        This setting will be rewrite by poor_DocumentRoot environ variable.
        """
        return self.__config['document_root']

    @document_root.setter
    def document_root(self, value):
        self.__config['document_root'] = value

    @property
    def document_index(self):
        """Application document_root as another way how to set poor_DocumentRoot.

        This setting will be rewrite by poor_DocumentRoot environ variable.
        """
        return self.__config['document_index'] == 'On'

    @document_index.setter
    def document_index(self, value):
        self.__config['document_index'] = 'On' if bool(value) else 'Off'

    @property
    def secret_key(self):
        """Application secret_key could be replace by poor_SecretKey in request.

        Secret key is used by PoorSession class. It is generate from
        some server variables, and the best way is set to your own long
        key."""
        return self.__config['secret_key']

    @secret_key.setter
    def secret_key(self, value):
        self.__config['secret_key'] = value

    @property
    def keep_blank_values(self):
        """Keep blank values in request arguments.

        If it is 1 (0 is default), automatic parsing request uri or body
        keep blank values as empty string.
        """
        return self.__config['keep_blank_values']

    @keep_blank_values.setter
    def keep_blank_values(self, value):
        self.__config['keep_blank_values'] = int(value)

    @property
    def strict_parsing(self):
        """Strict parse request arguments.

        If it is 1 (0 is default), automatic parsing request uri or body
        raise with exception on parsing error.
        """
        return self.__config['strict_parsing']

    @strict_parsing.setter
    def strict_parsing(self, value):
        self.__config['strict_parsing'] = int(value)

    @property
    def json_content_types(self):
        """Copy of json content type list.

        Containt list of strings as json content types, which is use for
        testing, when automatics Json object is create from request body.
        """
        return self.__config['json_content_types']

    @property
    def form_content_types(self):
        """Copy of form content type list.

        Containt list of strings as form content types, which is use for
        testing, when automatics Form object is create from request body.
        """
        return self.__config['form_content_types']

    def set_filter(self, name, regex, convertor=uni):
        """Create new filter or overwrite builtins.

        Arguments:
            name      - Name of filter which is used in route or set_route
                        method.
            regex     - regular expression which used for filter
            convertor - convertor function or class, which gets unicode in
                        input. Default is uni function, which is wrapper
                        to unicode string.

            app.set_filter('uint', r'\d+', int)
        """
        name = ':'+name if name[0] != ':' else name
        self.__filters[name] = (regex, convertor)

    def pre_process(self):
        """Append pre process hendler.

        This is decorator for function to call before each request.

            @app.pre_process()
            def before_each_request(req):
                ...
        """
        def wrapper(fn):
            self.__pre.append(fn)
            return fn
        return wrapper
    # enddef

    def add_pre_process(self, fn):
        """Append pre proccess handler.

        Method adds function to list functions which is call before each
        request.

            app.add_pre_process(before_each_request)
        """
        self.__pre.append(fn)
    # enddef

    def post_process(self):
        """Append post process handler.

        This decorator append function to be called after each request,
        if you want to use it redefined all outputs.

            @app.pre_process()
            def after_each_request(req):
                ...
        """
        def wrapper(fn):
            self.__post.append(fn)
            return fn
        return wrapper
    # enddef

    def add_post_process(self, fn):
        """Append post process handler.

        Method for direct append function to list functions which are called
        after each request.

            app.add_post_process(after_each_request)
        """
        self.__post.append(fn)
    # enddef

    def default(self, method=METHOD_HEAD | METHOD_GET):
        """Set default handler.

        This is decorator for default handler for http method (called before
        error_not_found).

            @app.default(METHOD_GET_POST)
            def default_get_post(req):
                # this function will be called if no uri match in internal
                # uri table with method. It's similar like not_found error,
                # but without error
                ...
        """
        def wrapper(fn):
            self.set_default(fn, method)
        return wrapper
    # enddef

    def set_default(self, fn, method=METHOD_HEAD | METHOD_GET):
        """Set default handler.

        Set fn default handler for http method called befor error_not_found.

            app.set_default(default_get_post, METHOD_GET_POST)
        """
        for m in methods.values():
            if method & m:
                self.__dhandlers[m] = fn
    # enddef

    def pop_default(self, method):
        """Pop default handler for method."""
        return self.__dhandlers(method)

    def route(self, uri, method=METHOD_HEAD | METHOD_GET):
        """Wrap function to be handler for uri and specified method.

        You can define uri as static path or as groups which are hand
        to handler as next parameters.

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
        you can use **kwargs syntax:

            @app.route('/<class>/<len:int>')
            def classes(req, **kwargs):
                return "'%s' class is %d lenght." % \
                    (kwargs['class'], kwargs['len'])

        Be sure with ordering of call this decorator or set_route function with
        groups regular expression. Regular expression routes are check with the
        same ordering, as you create internal table of them. First match stops
        any other searching. In fact, if groups are detect, they will be
        transfer to normal regular expression, and will be add to second
        internal table.
        """
        def wrapper(fn):
            self.set_route(uri, fn, method)
            return fn
        return wrapper
    # enddef

    def set_route(self, uri, fn, method=METHOD_HEAD | METHOD_GET):
        """Set handler for uri and method.

        Another way to add fn as handler for uri. See Application.route
        documentation for details.

            app.set_route('/use/post', user_create, METHOD_POST)
        """
        uri = uni(uri)

        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            convertors = tuple((g[0], self.__convertor(g[1]))
                               for g in (m.groups()
                               for m in re_filter.finditer(uri)))
            self.set_rroute(r_uri, fn, method, convertors)
        else:
            if uri not in self.__handlers:
                self.__handlers[uri] = {}
            for m in methods.values():
                if method & m:
                    self.__handlers[uri][m] = fn
    # enddef

    def pop_route(self, uri, method):
        """Pop handler for uri and method from handers table.

        Method must be define unique, so METHOD_GET_POST could not be use.
        If you want to remove handler for both methods, you must call pop route
        for each method state.
        """
        uri = uni(uri)

        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            return self.pop_rroute(r_uri, method)
        else:
            handlers = self.__handlers.get(uri, {})
            rv = handlers.pop(method)
            if not handlers:    # is empty
                self.__handlers.pop(uri, None)
            return rv

    def is_route(self, uri):
        """Check if uri have any registered record."""
        uri = uni(uri)
        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            return self.is_rroute(r_uri)
        return uri in self.__handlers

    def rroute(self, ruri, method=METHOD_HEAD | METHOD_GET):
        """Wrap function to be handler for uri defined by regular expression.

        Both of function, rroute and set_rroute store routes to special
        internal table, which is another to table of static routes.

            @app.rroute(r'/user/\w+')               # simple regular expression
            def any_user(req):
                ...

            @app.rroute(r'/user/(?P<user>\w+)')     # regular expression with
            def user_detail(req, user):             # groups
                ...

        Be sure with ordering of call this decorator or set_rroute function.
        Regular expression routes are check with the same ordering, as you
        create internal table of them. First match stops any other searching.
        """
        def wrapper(fn):
            self.set_rroute(ruri, fn, method)
            return fn
        return wrapper
    # enddef

    def set_rroute(self, r_uri, fn, method=METHOD_HEAD | METHOD_GET,
                   convertors=()):
        """Set hanlder for uri defined by regular expression.

        Another way to add fn as handler for uri defined by regular expression.
        See Application.rroute documentation for details.

            app.set_rroute('/use/\w+/post', user_create, METHOD_POST)

        This method is internally use, when groups are found in static route,
        adding by route or set_route method.
        """
        r_uri = re.compile(r_uri, re.U)
        if r_uri not in self.__rhandlers:
            self.__rhandlers[r_uri] = {}
        for m in methods.values():
            if method & m:
                self.__rhandlers[r_uri][m] = (fn, convertors)
    # enddef

    def pop_rroute(self, r_uri, method):
        """Pop handler and convertors for uri and method from handlers table.

        For mor details see Application.pop_route.
        """
        r_uri = re.compile(r_uri, re.U)
        handlers = self.__rhandlers.get(r_uri, {})
        rv = handlers.pop(method)
        if not handlers:    # is empty
            self.__rhandlers.pop(r_uri, None)
        return rv

    def is_rroute(self, r_uri):
        """Check if regular expression uri have any registered record."""
        r_uri = re.compile(r_uri, re.U)
        return r_uri in self.__rhandlers

    def http_state(self, code, method=METHOD_HEAD | METHOD_GET | METHOD_POST):
        """Wrap function to handle http status codes like http errors."""
        def wrapper(fn):
            self.set_http_state(code, fn, method)
        return wrapper
    # enddef

    def set_http_state(self, code, fn,
                       method=METHOD_HEAD | METHOD_GET | METHOD_POST):
        """Set fn as handler for http state code and method."""
        if code not in self.__shandlers:
            self.__shandlers[code] = {}
        for m in methods.values():
            if method & m:
                self.__shandlers[code][m] = fn
    # enddef

    def pop_http_state(self, code, method):
        """Pop handerl for http state and method.

        As Application.pop_route, for pop multimethod handler, you must call
        pop_http_state for each method.
        """
        handlers = self.__shandlers(code, {})
        return handlers.pop(method)

    def error_from_table(self, req, code):
        """Internal method, which is called if error was accured.

        If status code is in Application.shandlers (fill with http_state
        function), call this handler.
        """
        if code in self.__shandlers \
                and req.method_number in self.__shandlers[code]:
            try:
                handler = self.__shandlers[code][req.method_number]
                if 'uri_handler' not in req.__dict__:
                    req.uri_rule = '_%d_error_handler_' % code
                    req.uri_handler = handler
                self.handler_from_pre(req)       # call pre handlers now
                handler(req)
            except:
                internal_server_error(req)
        elif code in default_shandlers:
            handler = default_shandlers[code][METHOD_GET]
            handler(req)
        else:
            not_implemented(req, code)
    # enddef

    def handler_from_default(self, req):
        """Internal method, which is called if no handler is found."""
        if req.method_number in self.__dhandlers:
            req.uri_rule = '_default_handler_'
            req.uri_handler = self.__dhandlers[req.method_number]
            self.handler_from_pre(req)       # call pre handlers now
            retval = self.__dhandlers[req.method_number](req)
            if retval != DECLINED:
                raise SERVER_RETURN(retval)
    # enddef

    def handler_from_pre(self, req):
        """Internal method, which run all pre (pre_proccess) handlers.

        This method was call before end-point route handler.
        """
        for fn in self.__pre:
            fn(req)

    def handler_from_table(self, req):
        """Call right handler from handlers table (fill with route function).

        If no handler is fined, try to find directory or file if Document Root,
        resp. Document Index is set. Then try to call default handler for right
        method or call handler for status code 404 - not found.
        """

        # static routes
        if req.uri in self.__handlers:
            if req.method_number in self.__handlers[req.uri]:
                handler = self.__handlers[req.uri][req.method_number]
                req.uri_rule = req.uri      # nice variable for pre handlers
                req.uri_handler = handler
                self.handler_from_pre(req)  # call pre handlers now
                retval = handler(req)       # call right handler now
                # return text is allowed
                if isinstance(retval, str) \
                        or (_unicode_exist and isinstance(retval, unicode)):
                    req.write(retval, 1)    # write data and flush
                    retval = DONE
                if retval != DECLINED:
                    raise SERVER_RETURN(retval or DONE)  # could be state.DONE
            else:
                raise SERVER_RETURN(HTTP_METHOD_NOT_ALLOWED)
            # endif
        # endif

        # regular expression
        for ruri in self.__rhandlers.keys():
            match = ruri.match(req.uri)
            if match and req.method_number in self.__rhandlers[ruri]:
                handler, convertors = self.__rhandlers[ruri][req.method_number]
                req.uri_rule = ruri.pattern  # nice variable for pre handlers
                req.uri_handler = handler
                self.handler_from_pre(req)   # call pre handlers now
                if len(convertors):
                    # create OrderedDict from match insead of dict for
                    # convertors applying
                    req.groups = OrderedDict(
                        (g, c(v))for ((g, c), v) in zip(convertors,
                                                        match.groups()))
                    retval = handler(req, *req.groups.values())
                else:
                    req.groups = match.groupdict()
                    retval = handler(req, *match.groups())
                # return text is allowed
                if isinstance(retval, str) \
                        or (_unicode_exist and isinstance(retval, unicode)):
                    req.write(retval, 1)    # write data and flush
                    retval = DONE
                if retval != DECLINED:
                    raise SERVER_RETURN(retval or DONE)  # could be state.DONE
            # endif - no METHOD_NOT_ALLOWED here
        # endfor

        # try file or index
        if req.document_root():
            rfile = "%s%s" % (uni(req.document_root()),
                              path.normpath("%s" % uni(req.uri)))

            if not path.exists(rfile):
                if req.debug and req.uri == '/debug-info':      # work if debug
                    req.uri_rule = '_debug_info_'
                    req.uri_handler = debug_info
                    self.handler_from_pre(req)  # call pre handlers now
                    raise SERVER_RETURN(debug_info(req, self))
                self.handler_from_default(req)                  # try default
                raise SERVER_RETURN(HTTP_NOT_FOUND)             # not found

            # return file
            if path.isfile(rfile) and access(rfile, R_OK):
                req.uri_rule = '_send_file_'
                req.uri_handler = send_file
                self.handler_from_pre(req)      # call pre handlers now
                req.log_error("Return file: %s" % req.uri, LOG_INFO)
                raise SERVER_RETURN(send_file(req, rfile))

            # return directory index
            if req.document_index and path.isdir(rfile) \
                    and access(rfile, R_OK):
                req.log_error("Return directory: %s" % req.uri, LOG_INFO)
                req.uri_rule = '_directory_index_'
                req.uri_handler = directory_index
                self.handler_from_pre(req)      # call pre handlers now
                raise SERVER_RETURN(directory_index(req, rfile))

            raise SERVER_RETURN(HTTP_FORBIDDEN)
        # endif

        if req.debug and req.uri == '/debug-info':
            req.uri_rule = '_debug_info_'
            req.uri_handler = debug_info
            self.handler_from_pre(req)          # call pre handlers now
            raise SERVER_RETURN(debug_info(req, self))

        self.handler_from_default(req)

        req.log_error("404 Not Found: %s" % req.uri, LOG_ERR)
        raise SERVER_RETURN(HTTP_NOT_FOUND)
    # enddef

    def __request__(self, environ, start_response):
        """Create Request instance and return wsgi response.

        This method create Request object, call handlers from
        Application.__pre (Application.handler_from_pre),
        uri handler (handler_from_table), default handler
        (Application.handler_from_default) or error handler
        (Application.error_from_table), and handlers from
        Application.__post.
        """
        req = Request(environ, start_response, self.__config)

        try:
            self.handler_from_table(req)
        except SERVER_RETURN as e:
            code = e.args[0]
            if code in (OK, HTTP_OK, DONE):
                pass
            # XXX: elif code in (HTTP_MOVED_PERMANENTLY,
            #                    HTTP_MOVED_TEMPORARILY):
            else:
                req.status = code
                self.error_from_table(req, code)
        except (BrokenClientConnection, SystemExit) as e:
            req.log_error(str(e), LOG_ERR)
            req.log_error('   ***   You shoud ignore next error   ***',
                          LOG_ERR)
            return ()
        except:
            self.error_from_table(req, 500)
        # endtry

        try:    # call post_process handler
            for fn in self.__post:
                fn(req)
        except:
            self.error_from_table(req, 500)
        # endtry

        return req.__end_of_request__()    # private call of request
    # enddef

    def __call__(self, environ, start_response):
        """Callable define for Application instance.

        This method run __request__ method.
        """
        if self.__name == '__poorwsgi__':
            stderr.write("[W] Using deprecated instance of Application.\n")
            stderr.write("    Please, create your own instance\n")
            stderr.flush()
        return self.__request__(environ, start_response)

    def __profile_request__(self, environ, start_response):
        """Profiler version of __request__.

        This method is used if set_profile is used."""
        def wrapper(rv):
            rv.append(self.__original_request__(environ, start_response))

        rv = []
        uri_dump = (self._dump + environ.get('PATH_INFO').replace('/', '_')
                    + '.profile')
        self.log_error('Generate %s' % uri_dump, LOG_INFO)
        self._runctx('wrapper(rv)', globals(), locals(), filename=uri_dump)
        return rv[0]
    # enddef

    def __repr__(self):
        return '%s - callable Application class instance' % self.__name

    def set_profile(self, runctx, dump):
        """Set profiler for __call__ function.

        Arguments:
            runctx - function from profiler module
            dump - path and prefix for .profile files

        Typical usage:

            import cProfile

            cProfile.runctx('from simple import *', globals(), locals(),
                            filename="log/init.profile")
            app.set_profile(cProfile.runctx, 'log/req')
        """
        self._runctx = runctx
        self._dump = dump

        self.__original_request__ = self.__request__
        self.__request__ = self.__profile_request__
    # enddef

    def del_profile(self):
        """Remove profiler from application."""
        self.__request__ = self.__original_request__

    def get_options(self):
        """Returns dictionary with application variables from system environment.

        Application variables start with {app_} prefix,
        but in returned dictionary is set without this prefix.

            #!ini
            poor_LogLevel = warn        # Poor WSGI variable
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
    # enddef

    def log_error(self, message, level=LOG_ERR):
        """Logging method with the same functionality like in Request object.

        But as get_options read configuration from os.environ which could
        not work in same wsgi servers like Apaches mod_wsgi.

        This method write to stderr so messages, could not be found in
        servers error log!
        """
        if self.__log_level[0] >= level[0]:
            if _unicode_exist and isinstance(message, unicode):
                message = message.encode('utf-8')
            try:
                stderr.write("<%s> [%s] %s\n" % (level[1], self.__name,
                                                 message))
            except UnicodeEncodeError:
                if _unicode_exist:
                    message = message.decode('utf-8').encode(
                        'ascii', 'backslashreplace')
                else:
                    message = message.encode(
                        'ascii', 'backslashreplace').decode('ascii')

                stderr.write("<%s> [%s] %s\n" % (level[1], self.__name,
                                                 message))
            stderr.flush()
    # enddef

    def log_info(self, message):
        """Logging method, which create message as LOG_INFO level."""
        self.log_error(message, LOG_INFO)

    def log_debug(self, message):
        """Logging method, which create message as LOG_DEBUG level."""
        self.log_error(message, LOG_DEBUG)

    def log_warning(self, message):
        """Logging method, which create message as LOG_WARNING level."""
        self.log_error(message, LOG_WARNING)
# endclass
