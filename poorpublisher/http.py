from mod_python.apache import *

METHOD_POST     = 1
METHOD_GET      = 2
METHOD_GET_POST = 3
METHOD_HEAD     = 4

methods = {
    'POST': METHOD_POST,
    'GET' : METHOD_GET,
    'HEAD': METHOD_HEAD
}
