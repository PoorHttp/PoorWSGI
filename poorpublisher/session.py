#
# $Id$
#

from Cookie import SimpleCookie
from hashlib import sha1
from time import time
from pickle import dumps, loads
from base64 import b64decode, b64encode
from exceptions import NotImplementedError
from types import DictType

from mod_python.apache import APLOG_INFO

import bz2

def hidden(text, passwd):
    passwd = sha1(passwd).digest()
    passlen = len(passwd)
    retval = ''
    for i in xrange(len(text)):
        retval += chr(ord(text[i]) ^ ord(passwd[i % passlen]))
    return retval
#enddef

class PoorSession:
    def __init__(self, req, expires = 0, path = '/', SID = 'SESSID', get = None):
        self.SID = SID
        self.expires = expires
        self.path = path
        self.cookie = SimpleCookie()
        self.data = {}

        raw = None

        # get SID from cookie or url
        if not req.subprocess_env.has_key("SERVER_SOFTWARE"):
            req.add_common_vars()

        if req.subprocess_env.has_key("HTTP_COOKIE"):
            self.cookie.load(req.subprocess_env["HTTP_COOKIE"])
            if self.cookie.has_key(SID):
                raw = self.cookie[SID].value
        elif get:
            raw = get
        #endif
        

        if raw:
            try:
                self.data = loads(hidden(bz2.decompress(b64decode(raw)),
                                    req.secret_key))
                if type(self.data) != DictType:
                    raise RuntimeError()
            except:
                req.log_error('Bad session data.')
            #endtry

            if 'expires' in self.data and self.data['expires'] < int(time()):
                req.log_error('Session was expired, generating new.', APLOG_INFO)
                self.data = {}
            #endif
        #endif

    #enddef

    def renew(self):
        if self.expires:
            self.data['expires'] = int(time()) + self.expires
            return

        if 'expires' in self.data:
            self.data.pop('expires')
    #enddef

    def write(self, req):
        if self.expires:
            self.data['expires'] = int(time()) + self.expires
            self.cookie[self.SID]['expires'] = int(time()) + self.expires

        raw = b64encode(bz2.compress(hidden(dumps(self.data),
                                     req.secret_key), 9))
        self.cookie[self.SID] = raw
        self.cookie[self.SID]['path'] = self.path
            
        return True
    #enddef

    def destroy(self):
        self.data['expires'] = -1
        self.cookie[self.SID]['expires'] = -1
    #enddef

    def header(self, req, headers_out = None):
        self.write(req)
        cookies = self.cookie.output().split('\r\n')
        header = []
        for cookie in cookies:
            var = cookie[:10] # Set-Cookie
            val = cookie[12:] # SID=###; expires=###; Path=/
            header.append((var,val))
            if headers_out != None:
                headers_out.add(var, val)
        return header
    #enddef
#endclass
