"""
main application function, and functions for working with dispatch table
"""

from socket import error as SocketError
from os import path, access, R_OK
from collections import OrderedDict
from sys import version_info
import re

from poorwsgi.state import OK, DONE, DECLINED, HTTP_ERROR, HTTP_OK, \
            METHOD_GET, METHOD_POST, METHOD_HEAD, methods, LOG_INFO, LOG_ERR, \
            HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, \
            __author__, __date__, __version__
from poorwsgi.request import Request, uni
from poorwsgi.results import default_shandlers, not_implemented, internal_server_error, \
            SERVER_RETURN, send_file, directory_index, debug_info

re_filter = re.compile(r'<(\w+)(:[^>]+)?>')

if version_info.major < 3:      # python 2.x
    _unicode_exist = True
else:                           # python 3.x
    _unicode_exist = False

class Application:
    """ Poor WSGI application which is called by WSGI server, how, is describe
        in PEP 0333. This object store route dispatch table, and have methods
        for it's using and of course __call__ method for use as WSGI application.
    """
    def __init__(self):
        # list of pre and post process handlers
        self.__pre = []
        self.__post = []

        # dhandlers table for default handers on methods {METHOD_GET: handler}
        self.__dhandlers = {}

        # handlers table of simple paths: {'/path': {METHOD_GET: handler}}
        self.__handlers = {}

        self.__filters = {
            ':int'      : (r'-?\d+', int),
            ':float'    : (r'-?\d+(\.\d+)?', float),
            ':word'     : (r'\w+', uni),
            ':re:'      : (None, uni),
            'none'      : (r'[^/]+', uni)
        }

        # handlers table of regex paths: {r'/user/([a-z]?)': {METHOD_GET: handler}}
        self.__rhandlers = OrderedDict()

        # http state handlers table : {HTTP_NOT_FOUND: {METHOD_GET: my_404_handler}}
        self.__shandlers = {}
    #enddef

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
                raise RuntimeError("Undefined route group filter '%s'" % _filter)

        return "(?P<%s>%s)" % (groups[0], regex)
    #enddef

    def __convertor(self, _filter):
        _filter = str(_filter).lower()
        _filter = ':re:' if _filter[:4] == ':re:' else _filter
        try:
            return self.__filters[_filter][1]
        except KeyError:
            raise RuntimeError("Undefined route group filter '%s'" % _filter)

    @property
    def filters(self):
        return self.__filters.copy()

    def set_filter(self, name, regex, convertor = uni):
        """
        Set filter - create new or overwrite some builtin.
            name      - name of filter which is used in route or set_route method
            regex     - regular expression which used for filter
            convertor - convertor function or class, which gets unicode in input.
                        Default is uni function.

            app.set_filter('uint', r'\d+', int)
        """
        name = ':'+name if name[0] != ':' else name
        self.__filters[name] = (regex, convertor)

    def pre_process(self):
        """
            wrap function to call before each request

                @app.pre_process()
                def before_each_request(req):
                    ...
        """
        def wrapper(fn):
            self.__pre.append(fn)
            return fn
        return wrapper
    #enddef

    def add_pre_process(self, fn):
        """
            adds function to list functions which is call before each request

                app.add_pre_process(before_each_request)
        """
        self.__pre.append(fn)
    #enddef


    def post_process(self, req):
        """
        This method is called after each request, if you want to use it, just
        simple redefined it.

            @app.pre_process()
            def after_each_request(req):
                ...
        """
        def wrapper(fn):
            self.__post.append(fn)
            return fn
        return wrapper
    #enddef

    def add_post_process(self, fn):
        """
            adds function to list functions which is call before each request

                app.add__post_process(after_each_request)
        """
        self.__post.append(fn)

    @property
    def pre(self):
        return self.__pre.copy()

    @property
    def post(self):
        return self.__post.copy()

    @property
    def dhandlers(self):
        return self.__dhandlers.copy()

    @property
    def handlers(self):
        return self.__handlers.copy()

    @property
    def rhandlers(self):
        return self.__rhandlers.copy()

    @property
    def shandlers(self):
        return self.__shandlers.copy()


    def default(self, method = METHOD_HEAD | METHOD_GET):
        """
            wrap default handler (called before error_not_found) by method

                @app.default(METHOD_GET_POST)
                def default_get_post(req):
                    # this function will be called if no uri match in internal
                    # uri table with method. It's similar like not_found error,
                    # but without error
                    ...
        """
        def wrapper(fn):
            for m in methods.values():
                if method & m: self.__dhandlers[m] = fn
            return fn
        return wrapper
    #enddef

    def set_default(self, fn, method = METHOD_HEAD | METHOD_GET):
        """
            set fn as default handler for method

                app.set_default(default_get_post, METHOD_GET_POST)
        """
        for m in methods.values():
            if method & m: self.__dhandlers[m] = fn
    #enddef

    def route(self, uri, method = METHOD_HEAD | METHOD_GET):
        """
        Wrap function to be handler for uri and specified method. You can define
        uri as static path or as groups which are hand to handler as next
        parameters.

            # static uri
            @app.route('/user/post', method = METHOD_POST)
            def user_create(req):
                ...

            # group regular expression
            @app.route('/user/<name>')
            def user_detail(req, name):
                ...

            # group regular expression with filter
            @app.route('/<surname:word>'/<age:int>)
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
                return "'%s' class is %d lenght." % (kwargs['class'], kwargs['len'])


        """
        def wrapper(fn):
            self.set_route(uri, fn, method)
            return fn
        return wrapper
    #enddef

    def set_route(self, uri, fn, method = METHOD_HEAD | METHOD_GET):
        """
        Another way to add fn as handler for uri. See route documentation for
        details.

            app.set_route('/use/post', user_create, METHOD_POST)
        """
        uri = uni(uri)

        if re_filter.search(uri):
            r_uri = re_filter.sub(self.__regex, uri) + '$'
            convertors = tuple((g[0], self.__convertor(g[1])) \
                                     for g in (m.groups() for m in re_filter.finditer(uri)))
            self.set_rroute(r_uri, fn, method, convertors)
        else:
            if not uri in self.__handlers: self.__handlers[uri] = {}
            for m in methods.values():
                if method & m: self.__handlers[uri][m] = fn
    #enddef

    def rroute(self, ruri, method = METHOD_HEAD | METHOD_GET):
        """
        Wrap function to be handler for uri defined by regular expression and
        specified method.

            @app.rroute(r'/user/\w+')               # simple regular expression
            def any_user(req):
                ...

            @app.rroute(r'/user/(?P<user>\w+)')     # regular expression with groups
            def user_detail(req, user):
                ...
                
        Be sure with ordering of call this decorator or set_rroute function.
        Regular expression routes are check with the same ordering, as you
        create internal table of them. First match stops any other searching.
        """
        def wrapper(fn):
            self.set_rroute(ruri, fn, method)
            return fn
        return wrapper
    #enddef

    def set_rroute(self, r_uri, fn, method = METHOD_HEAD | METHOD_GET, convertors = ()):
        """
        Another way to add fn as handler for uri defined by regular expression.
        See rroute documentation for details.

            app.set_rroute('/use/\w+/post', user_create, METHOD_POST)
        """
        r_uri = re.compile(r_uri, re.U)
        if not r_uri in self.__rhandlers: self.__rhandlers[r_uri] = {}
        for m in methods.values():
            if method & m: self.__rhandlers[r_uri][m] = (fn, convertors)
    #enddef


    def http_state(self, code, method = METHOD_HEAD | METHOD_GET | METHOD_POST):
        """ wrap function to handle another http status codes like http errors """
        def wrapper(fn):
            if not code in self.__shandlers: self.__shandlers[code] = {}
            for m in methods.values():
                if method & m: self.__shandlers[code][m] = fn
            return fn
        return wrapper
    #enddef

    def set_http_state(self, code, fn, method = METHOD_HEAD | METHOD_GET | METHOD_POST):
        """ set fn as handler for http state code and method """
        if not code in self.__shandlers: self.__shandlers[code] = {}
        for m in methods.values():
            if method & m: self.__shandlers[code][m] = fn
    #enddef

    def error_from_table(self, req, code):
        """ this function is called if error was accured. If status code is in
            shandlers (fill with http_state function), call this handler.
        """
        if code in self.__shandlers and req.method_number in self.__shandlers[code]:
            try:
                handler = self.__shandlers[code][req.method_number]
                handler(req)
            except:
                internal_server_error(req)
        elif code in default_shandlers:
            handler = default_shandlers[code][METHOD_GET]
            handler(req)
        else:
            not_implemented(req)
    #enddef

    def handler_from_default(self, req):
        if req.method_number in self.__dhandlers:
            req.uri_rule = '_default_handler_'
            retval = self.__dhandlers[req.method_number](req)
            if retval != DECLINED:
                raise SERVER_RETURN(retval)
    #enddef

    def handler_from_table(self, req):
        """ call right handler from handlers table (fill with route function). If no
            handler is fined, try to find directory or file if Document Root, resp.
            Document Index is set. Then try to call default handler for right method
            or call handler for status code 404 - not found.
        """

        # static routes
        if req.uri in self.__handlers:
            if req.method_number in self.__handlers[req.uri]:
                handler = self.__handlers[req.uri][req.method_number]
                req.uri_rule = req.uri
                retval = handler(req)
                # return text is allowed
                if isinstance(retval, str) or (_unicode_exist and isinstance(retval, unicode)):
                    req.write(retval, 1)    # write data and flush
                    retval = DONE
                if retval != DECLINED:
                    raise SERVER_RETURN(retval or DONE)     # could be state.DONE
            else:
                raise SERVER_RETURN(HTTP_METHOD_NOT_ALLOWED)
            #endif
        #endif

        # regular expression
        for ruri in self.__rhandlers.keys():
            match = ruri.match(req.uri)
            if match and req.method_number in self.__rhandlers[ruri]:
                handler, convertors = self.__rhandlers[ruri][req.method_number]
                req.uri_rule = ruri.pattern
                if len(convertors):
                    # create OrderedDict from match insead of dict for convertors applying
                    req.groups = OrderedDict( (g, c(v)) for ((g, c), v) in zip(convertors, match.groups()) )
                    retval = handler(req, *req.groups.values())
                else:
                    req.groups = match.groupdict()
                    retval = handler(req, *match.groups())
                # return text is allowed
                if isinstance(retval, str) or (_unicode_exist and isinstance(retval, unicode)):
                    req.write(retval, 1)    # write data and flush
                    retval = DONE
                if retval != DECLINED:
                    raise SERVER_RETURN(retval or DONE)     # could be state.DONE
            #endif - no METHOD_NOT_ALLOWED here
        #endfor

        # try file or index
        if req.document_root():
            rfile = "%s%s" % (req.document_root(), path.normpath("%s" % req.uri))

            if not path.exists(rfile):
                if req.debug and req.uri == '/debug-info':      # work if debug
                    raise SERVER_RETURN(debug_info(req, self))
                self.handler_from_default(req)                  # try default
                raise SERVER_RETURN(HTTP_NOT_FOUND)             # not found

            # return file
            if path.isfile(rfile) and access(rfile, R_OK):
                req.log_error("Return file: %s" % req.uri, LOG_INFO);
                raise SERVER_RETURN(send_file(req, rfile))

            # return directory index
            if req.document_index and path.isdir(rfile) and access(rfile, R_OK):
                req.log_error("Return directory: %s" % req.uri, LOG_INFO);
                raise SERVER_RETURN(directory_index(req, rfile))

            raise SERVER_RETURN(HTTP_FORBIDDEN)
        #endif

        if req.debug and req.uri == '/debug-info':
            raise SERVER_RETURN(debug_info(req, self))

        self.handler_from_default(req)

        req.log_error("404 Not Found: %s" % req.uri, LOG_ERR);
        raise SERVER_RETURN(HTTP_NOT_FOUND)
    #enddef


    def __call__(self, environ, start_response):
        """ This method create Request object, call pre_process function,
            handler_from_table, and post_process function. pre_process and
            post_process functions are not in try except block !
        """

        req = Request(environ, start_response)

        try: # call pre_process
            for fn in self.__pre:
                fn(req)
        except:
            self.error_from_table(req, 500)
            return req.__end_of_request__()
        #endtry

        try:
            self.handler_from_table(req)
        except SERVER_RETURN as e:
            code = e.args[0]
            if code in (OK, HTTP_OK, DONE):
                pass
            # XXX: elif code in (HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY):
            else:
                req.status = code
                self.error_from_table(req, code)
        except SocketError as e:
            return ()
        except Exception as e:
            self.error_from_table(req, 500)
        #endtry

        try: # call post_process handler
            for fn in self.__post:
                fn(req)
        except:
            self.error_from_table(req, 500)
        #endtry

        return req.__end_of_request__()    # private call of request
    #enddef

    def __profile_call__(self, environ, start_response):
        """
        Profiler version of call, which is used if set_profile method is call.
        """
        def wrapper(rv):
            rv.append(self.__clear_call__(environ, start_response))

        rv = []
        uri_dump = self._dump + environ.get('PATH_INFO').replace('/','_') + '.profile'
        self._runctx('wrapper(rv)', globals(), locals(), filename =  uri_dump)
        return rv[0]
    #enddef

    def __repr__(self):
        return 'callable Application class instance'

    def set_profile(self, runctx, dump):
        """ Set profiler for __call__ function.
            runctx - function from profiler module
            dump - path and prefix for .profile files
        """
        self._runctx = runctx
        self._dump = dump

        self.__clear_call__ = self.__call__
        self.__call__ = self.__profile_call__
    #enddef

    def del_profile(self):
        self.__call__ = self.__clear_call__

#endclass

# application callable instance, which is need by wsgi server
application = Application()

# short reference to application instance, which is need by wsgi server
app = application
