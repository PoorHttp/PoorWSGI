"""
constants like http status code, log levels and method types
"""
__author__  = "Ondrej Tuma (McBig) <mcbig@zeropage.cz>"
__date__    = "20 August 2013"
__version__ = "1.0"

OK          = 0
DONE        = 1
DECLINED    = 2
HTTP_ERROR  = 3

HTTP_CONTINUE                     = 100
HTTP_SWITCHING_PROTOCOLS          = 101
HTTP_PROCESSING                   = 102
HTTP_OK                           = 200
HTTP_CREATED                      = 201
HTTP_ACCEPTED                     = 202
HTTP_NON_AUTHORITATIVE            = 203
HTTP_NO_CONTENT                   = 204
HTTP_RESET_CONTENT                = 205
HTTP_PARTIAL_CONTENT              = 206
HTTP_MULTI_STATUS                 = 207
HTTP_MULTIPLE_CHOICES             = 300
HTTP_MOVED_PERMANENTLY            = 301
HTTP_MOVED_TEMPORARILY            = 302
HTTP_SEE_OTHER                    = 303
HTTP_NOT_MODIFIED                 = 304
HTTP_USE_PROXY                    = 305
HTTP_TEMPORARY_REDIRECT           = 307
HTTP_BAD_REQUEST                  = 400
HTTP_UNAUTHORIZED                 = 401
HTTP_PAYMENT_REQUIRED             = 402
HTTP_FORBIDDEN                    = 403
HTTP_NOT_FOUND                    = 404
HTTP_METHOD_NOT_ALLOWED           = 405
HTTP_NOT_ACCEPTABLE               = 406
HTTP_PROXY_AUTHENTICATION_REQUIRED= 407
HTTP_REQUEST_TIME_OUT             = 408
HTTP_CONFLICT                     = 409
HTTP_GONE                         = 410
HTTP_LENGTH_REQUIRED              = 411
HTTP_PRECONDITION_FAILED          = 412
HTTP_REQUEST_ENTITY_TOO_LARGE     = 413
HTTP_REQUEST_URI_TOO_LARGE        = 414
HTTP_UNSUPPORTED_MEDIA_TYPE       = 415
HTTP_RANGE_NOT_SATISFIABLE        = 416
HTTP_EXPECTATION_FAILED           = 417
HTTP_UNPROCESSABLE_ENTITY         = 422
HTTP_LOCKED                       = 423
HTTP_FAILED_DEPENDENCY            = 424
HTTP_INTERNAL_SERVER_ERROR        = 500
HTTP_NOT_IMPLEMENTED              = 501
HTTP_BAD_GATEWAY                  = 502
HTTP_SERVICE_UNAVAILABLE          = 503
HTTP_GATEWAY_TIME_OUT             = 504
HTTP_VERSION_NOT_SUPPORTED        = 505
HTTP_VARIANT_ALSO_VARIES          = 506
HTTP_INSUFFICIENT_STORAGE         = 507
HTTP_NOT_EXTENDED                 = 510

LOG_EMERG   = (0, 'S') 
LOG_ALERT   = (1, 'A')
LOG_CRIT    = (2, 'C')
LOG_ERR     = (3, 'E')
LOG_WARNING = (4, 'W')
LOG_NOTICE  = (5, 'N')
LOG_INFO    = (6, 'I')
LOG_DEBUG   = (7, 'D')
LOG_NOERRNO = (8, '0')

levels = {
    'emerg' :   LOG_EMERG,
    'alert' :   LOG_ALERT,
    'crit'  :   LOG_CRIT,
    'error' :   LOG_ERR,
    'warn'  :   LOG_WARNING,
    'notice':   LOG_NOTICE,
    'info'  :   LOG_INFO,
    'debug' :   LOG_DEBUG
}

METHOD_HEAD     = 1
METHOD_GET      = 2
METHOD_POST     = 4
METHOD_PUT      = 8
METHOD_DELETE   = 16
METHOD_TRACE    = 32
METHOD_OPTIONS  = 64
METHOD_CONNECT  = 128
METHOD_PATCH    = 256

METHOD_GET_POST = METHOD_HEAD | METHOD_GET | METHOD_POST
METHOD_ALL      = 511 # METHOD_HEAD | ... | METHOD_PATCH

methods = {
    'HEAD'      : METHOD_HEAD,
    'GET'       : METHOD_GET,
    'POST'      : METHOD_POST,
    'PUT'       : METHOD_PUT,
    'DELETE'    : METHOD_DELETE,
    'TRACE'     : METHOD_TRACE,
    'OPTIONS'   : METHOD_OPTIONS,
    'CONNECT'   : METHOD_CONNECT,
    'PATCH'     : METHOD_PATCH
}

sorted_methods = sorted(methods.items(), key = lambda (k,v): (v,k))