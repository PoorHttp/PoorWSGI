#!/usr/bin/python

from exceptions import Exception
from socket import error as SocketError

import sys
    
from enums import *
from http import Request, internal_server_error, SERVER_RETURN

def error_from_dispatch(req, code):
    # set post_process handler if is possible
    if 'dispatch_table' in sys.modules and 'post_process' in dir(dispatch_table):
        dispatch_table.post_process(req)
    #endif

    if 'dispatch_table' in sys.modules \
    and 'errors' in dispatch_table.__dict__ \
    and code in dispatch_table.errors:
        try:
            handler = dispatch_table.errors[code]
            return handler(req)
        except:
            return internal_server_error(req)
    elif code == 500:
        return internal_server_error(req)
    return None
#enddef

def handler_from_dispatch(req):
    if not 'dispatch_table' in sys.modules:
        exec ("import dispatch_table") in globals()

    # call pre_process if is present
    if 'pre_process' in dir(dispatch_table):
        dispatch_table.pre_process(req)
    #endif

    if req.uri in dispatch_table.handlers:
        method, handler = dispatch_table.handlers[req.uri]
        # check if method is allowed
        if methods[req.method] & method:
            retval = handler(req)
            raise SERVER_RETURN, retval
        else:
            raise SERVER_RETURN, HTTP_METHOD_NOT_ALLOWED
        #endif
    #endif

    if 'default_handler' in dir(dispatch_table):
        retval = dispatch_table.default_handler(req)
        raise SERVER_RETURN, retval
   
    req.log_error("404 Not Found: %s" % req.uri, LOG_ERR);
    raise SERVER_RETURN, HTTP_NOT_FOUND
#enddef

def application(environ, start_response):
    req = Request(environ, start_response)
    try:
        handler_from_dispatch(req)
    except SERVER_RETURN, e:
        code = e.args[0]
        if code in (OK, HTTP_OK, DONE):
            pass
        # XXX: elif code in (HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY):
        else:
            req.status = code
    except SocketError, e:
        return ()
    except Exception, e:
        error_from_dispatch(req, 500)
    #endtry

    # set post_process handler if is possible
    if 'dispatch_table' in sys.modules and 'post_process' in dir(dispatch_table):
        dispatch_table.post_process(req)
    #endif

    return req.__end_of_request__()    # private call of request
#enddef
