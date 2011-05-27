#
# $Id$
#

from mod_python.apache import *
from session import *
from mod_python.util import FieldStorage as APFieldStorage, redirect
from traceback import format_exception

METHOD_POST     = 1
METHOD_GET      = 2
METHOD_GET_POST = 3
METHOD_HEAD     = 4

methods = {
    'POST': METHOD_POST,
    'GET' : METHOD_GET,
    'HEAD': METHOD_HEAD
}

LOG_EMERG   = APLOG_EMERG
LOG_ALERT   = APLOG_ALERT
LOG_CRIT    = APLOG_CRIT
LOG_ERR     = APLOG_ERR
LOG_WARNING = APLOG_WARNING
LOG_NOTICE  = APLOG_NOTICE
LOG_INFO    = APLOG_INFO
LOG_DEBUG   = APLOG_DEBUG
LOG_NOERRNO = APLOG_NOERRNO

class FieldStorage(APFieldStorage):
    def getfirst(self, name, default = None, fce = None):
        if fce:
            return fce(APFieldStorage.getfirst(self, name, default))
        return APFieldStorage.getfirst(self, name, default)
    #enddef
#endclass

def internal_server_error(req):
    """
    More debug internal server error (was called automaticly when no handlers
    is not defined and where __debug__ is true)
    """
    traceback = format_exception(sys.exc_type,
                                 sys.exc_value,
                                 sys.exc_traceback)

    traceback = ''.join(traceback)
    req.log_error("%s" % traceback, APLOG_ERR)
    traceback = traceback.split('\n')

    req.content_type = "text/html"
    req.status = HTTP_INTERNAL_SERVER_ERROR

    content = [
            "<html>\n",
            "  <head>\n",
            "    <title>500 - Internal Server Error</title>\n",
            "    <style>\n",
            "      body {width: 80%%; margin: auto; padding-top: 30px;}\n",
            "      pre .line1 {background: #e0e0e0}\n",
            "    </style>\n",
            "  <head>\n",
            "  <body>\n",
            "    <h1>500 - Internal Server Error</h1>\n",
    ]
    
    for l in content: req.write(l)

    if __debug__:
        content = [
            "    <h2>Exception Traceback</h2>\n",
            "    <pre>",
        ]
        for l in content: req.write(l)

        # Traceback
        for i in xrange(len(traceback)):
            req.write('<div class="line%s">%s</div>' % ( i % 2, traceback[i]))

    #endif
        
    content = [
        "  </body>\n",
        "</html>"
    ]

    for l in content: req.write(l)
    return DONE
#enddef
