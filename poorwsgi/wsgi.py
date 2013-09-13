#!/usr/bin/python

"""
main application function, and functions for working with dispatch table
"""

from socket import error as SocketError

import sys, os

from state import OK, DONE, DECLINED, HTTP_ERROR, HTTP_OK, \
            METHOD_GET, METHOD_POST, METHOD_HEAD, methods, LOG_INFO, LOG_ERR, \
            HTTP_METHOD_NOT_ALLOWED
from request import Request, SERVER_RETURN
from results import default_shandlers, not_implemented, internal_server_error, \
            send_file, directory_index, debug_info

def pre_process(req):
    """
    This method is called before each request, if you want to use it, just
    simple redefined it.
    """
    pass

def post_process(req):
    """
    This method is called after each request, if you want to use it, just
    simple redefined it.
    """
    pass

# dhandlers table for default handers on methods {METHOD_GET: handler}
dhandlers = {}

# handlers table of simple paths: {'/path': {METHOD_GET: handler}}
handlers = {}

# handlers table of regex paths: {r'/user/([a-z]?)': {METHOD_GET: handler}}
rhandlers = {}

# http state handlers table : {HTTP_NOT_FOUND: {METHOD_GET: my_404_handler}}
shandlers = {}

def route(uri, method = METHOD_HEAD | METHOD_GET):
    """ wrap function to be handler for uri by method """
    def wrapper(fn):
        if not uri in handlers: handlers[uri] = {}
        for m in methods.values():
            if method & m: handlers[uri][m] = fn
        return fn
    return wrapper
#enddef

def set_route(uri, fn, method = METHOD_HEAD | METHOD_GET):
    """ set fn as handler for uri and method """
    if not uri in handlers: handlers[uri] = {}
    for m in methods.values():
        if method & m: handlers[uri][m] = fn
#enddef

def rroute():
    """ TODO: routes defined by regular expression """
    pass

def groute():
    """ TODO: routes defined by simple group regular expression """
    pass

def default(method = METHOD_HEAD | METHOD_GET):
    """ wrap default handler (called before error_not_found) by method """
    def wrapper(fn):
        for m in methods.values():
            if method & m: dhandlers[m] = fn
        return fn
    return wrapper
#enddef

def set_default(fn, method = METHOD_HEAD | METHOD_GET):
    """ set fn as default handler for method """
    for m in methods.values():
        if method & m: dhandlers[m] = fn
#enddef

def http_state(code, method = METHOD_HEAD | METHOD_GET | METHOD_POST):
    """ wrap function to handle another http status codes like http errors """
    def wrapper(fn):
        if not code in shandlers: shandlers[code] = {}
        for m in methods.values():
            if method & m: shandlers[code][m] = fn
        return fn
    return wrapper
#enddef

def set_http_state(code, fn, method = METHOD_HEAD | METHOD_GET | METHOD_POST):
    """ set fn as handler for http state code and method """
    if not code in shandlers: shandlers[code] = {}
    for m in methods.values():
        if method & m: shandlers[code][m] = fn
#enddef

def error_from_table(req, code):
    """ this function is called if error was accured. If status code is in
        shandlers (fill with http_state function), call this handler.
    """
    if code in shandlers and req.method in shandlers[code]:
        try:
            handler = shandlers[code][req.method]
            return handler(req)
        except:
            return internal_server_error(req)
    elif code in default_shandlers:
        handler = default_shandlers[code][METHOD_GET]
        handler(req)
    else:
        not_implemented(req)
#enddef

def handler_from_table(req):
    """ call right handler from handlers table (fill with route function). If no
        handler is fined, try to find directory or file if Document Root, resp.
        Document Index is set. Then try to call default handler for right method
        or call handler for status code 404 - not found.
    """

    if req.uri in handlers:
        req.log_error("handlers uri %s method %s" % (req.uri, str(handlers[req.uri]) ) )
        if req.method in handlers[req.uri]:
            handler = handlers[req.uri][req.method]
            retval = handler(req)
            if retval != DECLINED:
                raise SERVER_RETURN(retval)
        else:
            raise SERVER_RETURN(HTTP_METHOD_NOT_ALLOWED)
        #endif
    #endif
   
    # try file or index
    if req.document_root():
        rfile = "%s%s" % (req.document_root(), os.path.normpath("%s" % req.uri))
        
        if not os.access(rfile, os.R_OK):
            req.log_error("404 File Not Found: %s" % req.uri, LOG_ERR)
            raise SERVER_RETURN(HTTP_NOT_FOUND)

        if os.path.isfile(rfile):
            req.log_error("Return file: %s" % req.uri, LOG_INFO);
            raise SERVER_RETURN(send_file(req, rfile))

        # try directory index
        if req.document_index and os.path.isdir(rfile):
            req.log_error("Return directory: %s" % req.uri, LOG_INFO);
            raise SERVER_RETURN(directory_index(req, rfile))
        else:
            raise SERVER_RETURN(HTTP_FORBIDDEN)
    #endif

    if req.debug and req.uri == '/debug-info':
        raise SERVER_RETURN(debug_info(req, handlers, dhandlers, shandlers))

    # default handler is at the end of request - before 404 error
    if req.method in dhandlers:
        retval = dhandlers[req.method](req)
        if retval != DECLINED:
            raise SERVER_RETURN(retval)

    req.log_error("404 Not Found: %s" % req.uri, LOG_ERR);
    raise SERVER_RETURN(HTTP_NOT_FOUND)
#enddef

def application(environ, start_response):
    """ Poor WSGI application which is called by WSGI server, how is describe
        in PEP XXXX (http://xxx).
        This function create Request object, call pre_process function, 
        handler_from_table, and post_process function. pre_process and
        post_process functions are not in try except block !
    """
    req = Request(environ, start_response)

    # call pre_process
    pre_process(req)

    try:
        handler_from_table(req)
    except SERVER_RETURN as e:
        code = e.args[0]
        if code in (OK, HTTP_OK, DONE):
            pass
        # XXX: elif code in (HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY):
        else:
            req.status = code
            error_from_table(req, code)
    except SocketError as e:
        return ()
    except Exception as e:
        error_from_table(req, 500)
    #endtry

    # call post_process handler
    post_process(req)

    return req.__end_of_request__()    # private call of request
#enddef
