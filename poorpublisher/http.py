from mod_python.apache import *
from session import *
from mod_python.util import FieldStorage, redirect


METHOD_POST     = 1
METHOD_GET      = 2
METHOD_GET_POST = 3
METHOD_HEAD     = 4

methods = {
    'POST': METHOD_POST,
    'GET' : METHOD_GET,
    'HEAD': METHOD_HEAD
}

LOG_INFO    = APLOG_INFO
LOG_NOTICE  = APLOG_NOTICE
