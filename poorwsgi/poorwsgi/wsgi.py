"""
main application function, and functions for working with dispatch table
"""

from socket import error as SocketError
from os import path, access, R_OK

from state import OK, DONE, DECLINED, HTTP_ERROR, HTTP_OK, \
            METHOD_GET, METHOD_POST, METHOD_HEAD, methods, LOG_INFO, LOG_ERR, \
            HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, \
            __author__, __date__, __version__
from request import Request, SERVER_RETURN
from results import default_shandlers, not_implemented, internal_server_error, \
            send_file, directory_index, debug_info

class Application:
    """ Poor WSGI application which is called by WSGI server, how, is describe
        in PEP 0333 (http://www.python.org/dev/peps/pep-0333/).
        This object store route dispatch table, and have methods for it's using
        and of course __call__ method for use as WSGI application.
    """
    def __init__(self):
        # dhandlers table for default handers on methods {METHOD_GET: handler}
        self.dhandlers = {}

        # handlers table of simple paths: {'/path': {METHOD_GET: handler}}
        self.handlers = {}

        # handlers table of regex paths: {r'/user/([a-z]?)': {METHOD_GET: handler}}
        self.rhandlers = {}

        # http state handlers table : {HTTP_NOT_FOUND: {METHOD_GET: my_404_handler}}
        self.shandlers = {}
    #enddef

    def pre_process(self, req):
        """
        This method is called before each request, if you want to use it, just
        simple redefined it.
        """
        pass

    def post_process(self, req):
        """
        This method is called after each request, if you want to use it, just
        simple redefined it.
        """
        pass

    def default(self, method = METHOD_HEAD | METHOD_GET):
        """ wrap default handler (called before error_not_found) by method """
        def wrapper(fn):
            for m in methods.values():
                if method & m: self.dhandlers[m] = fn
            return fn
        return wrapper
    #enddef

    def set_default(self, fn, method = METHOD_HEAD | METHOD_GET):
        """ set fn as default handler for method """
        for m in methods.values():
            if method & m: self.dhandlers[m] = fn
    #enddef

    def route(self, uri, method = METHOD_HEAD | METHOD_GET):
        """ wrap function to be handler for uri by method """
        def wrapper(fn):
            if not uri in self.handlers: self.handlers[uri] = {}
            for m in methods.values():
                if method & m: self.handlers[uri][m] = fn
            return fn
        return wrapper
    #enddef

    def set_route(self, uri, fn, method = METHOD_HEAD | METHOD_GET):
        """ set fn as handler for uri and method """
        if not uri in self.handlers: self.handlers[uri] = {}
        for m in methods.values():
            if method & m: self.handlers[uri][m] = fn
    #enddef

    def rroute(self, ruri, method = METHOD_HEAD | METHOD_GET):
        """ TODO: routes defined by regular expression """
        NotImplementedError('Not implement yet')

    def set_rroute(self, ruri, method = METHOD_HEAD | METHOD_GET):
        """ TODO: routes defined by regular expression """
        NotImplementedError('Not implement yet')

    def groute(self, guri, method = METHOD_HEAD | METHOD_GET):
        """ TODO: routes defined by simple group regular expression """
        NotImplementedError('Not implement yet')

    def set_groute(self, guri, method = METHOD_HEAD | METHOD_GET):
        """ TODO: routes defined by simple group regular expression """
        NotImplementedError('Not implement yet')

    def http_state(self, code, method = METHOD_HEAD | METHOD_GET | METHOD_POST):
        """ wrap function to handle another http status codes like http errors """
        def wrapper(fn):
            if not code in self.shandlers: self.shandlers[code] = {}
            for m in methods.values():
                if method & m: self.shandlers[code][m] = fn
            return fn
        return wrapper
    #enddef

    def set_http_state(self, code, fn, method = METHOD_HEAD | METHOD_GET | METHOD_POST):
        """ set fn as handler for http state code and method """
        if not code in self.shandlers: self.shandlers[code] = {}
        for m in methods.values():
            if method & m: self.shandlers[code][m] = fn
    #enddef

    def error_from_table(self, req, code):
        """ this function is called if error was accured. If status code is in
            shandlers (fill with http_state function), call this handler.
        """
        if code in self.shandlers and req.method_number in self.shandlers[code]:
            try:
                handler = self.shandlers[code][req.method_number]
                handler(req)
            except:
                internal_server_error(req)
        elif code in default_shandlers:
            handler = default_shandlers[code][METHOD_GET]
            handler(req)
        else:
            not_implemented(req)
    #enddef

    def handler_from_table(self, req):
        """ call right handler from handlers table (fill with route function). If no
            handler is fined, try to find directory or file if Document Root, resp.
            Document Index is set. Then try to call default handler for right method
            or call handler for status code 404 - not found.
        """

        if req.uri in self.handlers:
            if req.method_number in self.handlers[req.uri]:
                handler = self.handlers[req.uri][req.method_number]
                retval = handler(req)
                if retval != DECLINED:
                    raise SERVER_RETURN(retval)
            else:
                raise SERVER_RETURN(HTTP_METHOD_NOT_ALLOWED)
            #endif
        #endif
   
        # try file or index
        if req.document_root():
            rfile = "%s%s" % (req.document_root(), path.normpath("%s" % req.uri))
        
            if not access(rfile, R_OK):
                req.log_error("404 File Not Found: %s" % req.uri, LOG_ERR)
                raise SERVER_RETURN(HTTP_NOT_FOUND)

            if path.isfile(rfile):
                req.log_error("Return file: %s" % req.uri, LOG_INFO);
                raise SERVER_RETURN(send_file(req, rfile))

            # try directory index
            if req.document_index and path.isdir(rfile):
                req.log_error("Return directory: %s" % req.uri, LOG_INFO);
                raise SERVER_RETURN(directory_index(req, rfile))
            else:
                raise SERVER_RETURN(HTTP_FORBIDDEN)
        #endif

        if req.debug and req.uri == '/debug-info':
            raise SERVER_RETURN(debug_info(req, self))

        # default handler is at the end of request - before 404 error
        if req.method_number in self.dhandlers:
            retval = self.dhandlers[req.method_number](req)
            if retval != DECLINED:
                raise SERVER_RETURN(retval)

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
            self.pre_process(req)
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
            self.post_process(req)
        except:
            self.error_from_table(req, 500)
        #endtry

        return req.__end_of_request__()    # private call of request
    #enddef

#endclass

application = Application()
app = application
