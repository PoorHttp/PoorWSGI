
from py_compile import compile
from http import methods, SERVER_RETURN, HTTP_INTERNAL_SERVER_ERROR, \
        HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_FOUND, OK
from mod_python.util import FieldStorage
from sys import modules

def error_from_dispatch(req, code):
    if 'dispatch_table' in modules \
    and 'errors' in dispatch_table.__dict__ \
    and code in dispatch_table.errors:
        try:
            handler = dispatch_table.errors[code]
            return handler(req)
        except:
            return HTTP_INTERNAL_SERVER_ERROR

    return code
#enddef

def handler(req):
    if not 'dispatch_table' in modules:
        exec("import dispatch_table") in globals()

    req.form = FieldStorage(req)

    # call setreq if is present
    if 'setreq' in dir(dispatch_table):
        dispatch_table.setreq(req)
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

        return error_from_dispatch(req, HTTP_NOT_FOUND)
    except SERVER_RETURN, e:
        raise e
    except:
        return error_from_dispatch(req, HTTP_INTERNAL_SERVER_ERROR)
#enddef
