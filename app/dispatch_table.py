#
# $Id: poorpublisher.py 16 2011-06-06 08:43:47Z ondratu $
#

import http
import re

from main import itworks

init = False
re_mail = None

def setreq(req):
    global re_mail
    global init

    if not init:
        re_mail = re.compile("^[a-z0-9\-_\.]+@[a-z0-9\-_\.]+$")

        req.log_error('Reinicalizace ...', http.LOG_DEBUG)
        init = True
    #endif
    
    req.re_mail = re_mail
#enddef

handlers = {
    '/'             : (http.METHOD_GET, itworks),
#    '/login'        : (http.METHOD_GET, main.login),
#    '/dologin'      : (http.METHOD_GET, main.dologin),
#    '/dologout'     : (http.METHOD_GET, main.dologout),
#    '/session'      : (http.METHOD_GET, main.session),
}
