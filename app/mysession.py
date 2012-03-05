from http import PoorSession, LOG_INFO, HTTP_MOVED_TEMPORARILY, SERVER_RETURN, \
                DONE
from time import time

def redirect (req, uri):
    url = req.construct_url(uri)

    req.status = HTTP_MOVED_TEMPORARILY
    req.headers_out.add('Location', url)

    req.write('Redirect to : %s' % url)
    raise SERVER_RETURN, DONE
#enddef

def doLogin(req, id, ip = None):
    cookie = PoorSession(req)
    cookie.data["id"] = id
    cookie.data["timestamp"] = int(time())
    if ip:
        cookie.data["ip"] = req.get_remote_host()
    cookie.header(req, req.headers_out)
    req.log_error("Login cookie was be set.", LOG_INFO)
#enddef
   
def doLogout(req):
    cookie = PoorSession(req)
    if not "id" in cookie.data:
        req.log_error("Login cookie not found.", LOG_INFO)
        return
    
    cookie.destroy()
    cookie.header(req, req.headers_out)
    req.log_error("Login cookie was be destroyed (Logout)", LOG_INFO)
#enddef

def checkLogin(req, redirectUri = None):
    cookie = PoorSession(req)
    if not "id" in cookie.data:
        req.log_error("Login cookie not found.", LOG_INFO)
        if redirectUri:
            redirect(req, redirectUri)
        return None

    if "ip" in cookie.data and cookie.data["ip"] != req.get_remote_host():
        cookie.destroy()
        cookie.header(req, req.headers_out)
        req.log_error("Login cookie was be destroyed (invalid IP address)",
                LOG_INFO)
        if redirectUri:
            redirect(req, redirectUri)
        return None

    return cookie
#enddef
