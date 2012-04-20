#
# $Id$
#
## \namespace http
#  http server compatitible interface

from mod_python.apache import *
from session import *
from mod_python.util import FieldStorage as APFieldStorage, redirect
from traceback import format_exception

## \defgroup http http server inetrface (Apache)
# @{

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
    """Field storage from mod_python with better getfirst method."""

    def getfirst(self, name, default = None, fce = None):
        """Returns value of key from \b GET or \b POST form.
        @param name key
        @param default default value if is not set
        @param fce function which processed value. For example str or int
        """
        if fce:
            return fce(APFieldStorage.getfirst(self, name, default))
        return APFieldStorage.getfirst(self, name, default)
    #enddef

    def getlist(self, name, fce = None):
        """Returns list of values of key from \b GET or \b POST form.
        @param name key
        @param fce function which processed value. For example str or int
        """
        if fce:
            return map(fce, APFieldStorage.getlist(self, name))
        return APFieldStorage.getlist(self, name)
    #enddef
#endclass

## @}

## \defgroup internal Internal Poor Publisher functions and classes
#  @{

def internal_server_error(req):
    """More debug internal server error handler. It was be called automaticly
    when no handlers are not defined in dispatch_table.errors. If __debug__ is
    true, Tracaback will be genarated.
    @param req mod_python.apache.request
    @returns http.DONE
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

## @}
