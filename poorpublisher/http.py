#
# $Id$
#

from mod_python.apache import *
from session import *
from mod_python.util import FieldStorage as APFieldStorage, redirect

METHOD_POST     = 1
METHOD_GET      = 2
METHOD_GET_POST = 3
METHOD_HEAD     = 4

methods = {
    'POST': METHOD_POST,
    'GET' : METHOD_GET,
    'HEAD': METHOD_HEAD
}

LOG_ERR     = APLOG_ERR
LOG_NOTICE  = APLOG_NOTICE
LOG_INFO    = APLOG_INFO

class FieldStorage(APFieldStorage):
    def getfirst(self, name, default = None, fce = None):
        if fce:
            return fce(APFieldStorage.getfirst(self, name, default))
        return APFieldStorage.getfirst(self, name, default)
    #enddef
#endclass
