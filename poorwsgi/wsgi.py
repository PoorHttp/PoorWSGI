#!/usr/bin/python

#from exceptions import Exception
from socket import error as SocketError

import sys, os

from state import *
from request import Request, SERVER_RETURN
from results import default_shandlers, not_implemented, internal_server_error, \
            send_file, directory_index, debug_info, DECLINED


def pre_process(req):
    # this method is called before each request
    pass

def post_process(req):
    # this method is called after each request
    pass

def default_handler(req):
    # this method is called if no url is match from handlers or rhandlers table
    pass

# default_handler is None, couse if would be function, i can't test his sets
default_handler = None

# handlers table of simple paths: {'/path/to/request': (METHOD_GET, handler)}
# TODO: {(uri, method): handler}
handlers = {}

# handlers table of regex paths: {r'/user/([a-z]?)': (METHOD_GET, handler)}
rhandlers = {}

# http state handlers table : {HTTP_NOT_FOUND: my_404_handler}
shandlers = {}

def route(uri, method = METHOD_HEAD | METHOD_GET):
    # wrap function to be handler for uri with method
    def wrapper (fn):
        global handlers
        handlers[uri] = (method, fn)
        return fn
    return wrapper
#enddef

def rroute():
    pass

def groute():
    pass

def default():
    # wrap default handler (before 404)
    def wrapper (fn):
        global default_handler
        default_handler = fn
        return fn
    return wrapper
#enddef

def http_state(code):
    # wrap function to be error handler for http code
    def wrapper (fn):
        global shandlers
        shandlers[code] = fn
        return fn
    return wrapper
#enddef

def error_from_table(req, code):
    # call post_process handler
    post_process(req)

    if code in shandlers:
        try:
            handler = shandlers[code]
            return handler(req)
        except:
            return internal_server_error(req)
    elif code in default_shandlers:
        handler = default_shandlers[code]
        handler(req)
    else:
        not_implemented(req)
#enddef

def handler_from_table(req):
    # call pre_process
    pre_process(req)

    if req.uri in handlers:
        method, handler = handlers[req.uri]
        # check if method is allowed
        if methods[req.method] & method:
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
        raise SERVER_RETURN(debug_info(req, handlers, default_handler, shandlers))

    # default handler is at the end of request - before 404 error
    if default_handler is not None:
        retval = default_handler(req)
        if retval != DECLINED:
            raise SERVER_RETURN(retval)

    req.log_error("404 Not Found: %s" % req.uri, LOG_ERR);
    raise SERVER_RETURN(HTTP_NOT_FOUND)
#enddef

def application(environ, start_response):
    req = Request(environ, start_response)
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
