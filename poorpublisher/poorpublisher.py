#
# $Id$
#

## \namespace poorpublisher
#  python handler definition

from http import methods, SERVER_RETURN, HTTP_INTERNAL_SERVER_ERROR, \
        HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, OK, internal_server_error, \
        APLOG_ERR
from sys import modules, path
from os import chdir
import dispatch_table

## \defgroup poorpublisher Poor Publisher
#  @{

def pre_process(req):
    pass

def post_process(req):
    pass

# set pre_process handler if is possible
if 'post_process' in dir(dispatch_table):
    post_process = dispatch_table.post_process
#endif

## Error handler of http errors. Another errors generate
#  500 Internal serverver error. If error 500 is return, and no handler is
#  defined in dispatch_table.errors dictionary http.internal_server_error 
#  called. This function is poorpublihser's internal.
def error_from_dispatch(req, code):
    # set post_process handler if is possible
    if 'post_process' in dir(dispatch_table):
        dispatch_table.post_process(req)
    #endif

    if 'dispatch_table' in modules \
    and 'errors' in dispatch_table.__dict__ \
    and code in dispatch_table.errors:
        try:
            handler = dispatch_table.errors[code]
            return handler(req)
        except:
            #return HTTP_INTERNAL_SERVER_ERROR
            return internal_server_error(req)
    
    elif code == HTTP_INTERNAL_SERVER_ERROR:
        return internal_server_error(req)
    return code
#enddef

def handler(req):
    """
    Main python handler function, which is called from apache mod_python.
    @param req mod_python.apache.request http://modpython.org/live/current/doc-html/pyapi-mprequest.html
    @throw <mod_python.apache.SERVER_RETURN> http error code exception
    \sa http://modpython.org/live/current/doc-html/pyapi-handler.html
    """
    #@TODO server_key by mel byt nastavitelny pres option v .htaccess !!
    req.secret_key = "$Id$"
    chdir(path[1])  # change directory to app  # XXX: tohle je spatne, nemusi to
                    # vzdy byt zrovna 1cka !!!
    
    # set pre_process handler if is possible
    if 'pre_process' in dir(dispatch_table):
        dispatch_table.pre_process(req)
    #endif

    try:
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

        req.log_error("uri '%s' not found." % req.uri, APLOG_ERR)
        return error_from_dispatch(req, HTTP_NOT_FOUND)
    except SERVER_RETURN, e:
        # set post_process handler if is possible
        if 'post_process' in dir(dispatch_table):
            dispatch_table.post_process(req)
        #endif
        raise e
    except:
        return error_from_dispatch(req, HTTP_INTERNAL_SERVER_ERROR)
#enddef

## @}
