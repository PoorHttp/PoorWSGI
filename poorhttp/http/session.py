
from Cookie import SimpleCookie
from sha import sha
from time import time
from pickle import dumps, loads
from base64 import b64decode, b64encode
from exceptions import NotImplementedError

import bz2

class Session:
    """
    Base Session class, data are store to DATA variable in cookie
    of if it not enable in server GET and POST variable.
    """

    def __init__(self, req, expires = 60*60, path = '/', SID = 'SESSID',
                                                         DATA = '_DATA'):
        self.SID = SID
        self.DATA = DATA
        self.id = None
        self.expires = expires
        self.cookie = SimpleCookie()

        # get SID from cookie or url
        if req.cookie:
            self.cookie.load(req.cookie)
            if self.cookie.has_key(SID):
                self.id = self.cookie[SID].value
        else:
            # XXX: this is not checked
            self.id = req.form.getvalue(SID)
        #endif
        
        self.create(req)

        # complete cookie
        self.cookie[SID] = self.id
        self.cookie[SID]['path'] = path
        self.cookie[SID]['expires'] = expires
    #enddef

    
    def create(self, req):
        if not self.id:
            self.id = sha("%s" % time()).hexdigest()
        return self.id
    #enddef

    def read(self, req):
        if self.cookie.has_key(self.DATA):
            b64 = self.cookie[self.DATA].value
            data = loads(bz2.decompress(b64decode(b64)))
        else:
            data = {}
        return data
    #enddef

    def write(self, req, data):
        b64 = b64encode(bz2.compress(dumps(data)))
        self.cookie[self.DATA] = b64
        self.cookie[self.DATA]['expires'] = self.expires
        return True
    #enddef

    def clean(self, req):
        self.cookie[self.DATA]['expires'] = -1
        return True
    #enddef

    def destroy(self, req):
        self.clean(req)
        self.cookie[self.SID]['expires'] = -1
    #enddef

    def header(self, req):
        req.SID = self.SID
        req.DATA = self.DATA
        cookies = self.cookie.output().split('\r\n')
        header = []
        for cookie in cookies:
            var = cookie[:10] # Set-Cookie
            val = cookie[12:] # SID=###; expires=###; Path=/
            header.append((var,val))
        return header
    #enddef

#endclass

class MCSession(Session):
    """
    Memcache session, data are stored to memcache server
    """
    def __init__(self, req, expires = 60*60, path = '/', SID = 'SESSID'):
        Session.__init__(self, req, expires, path, SID)
    #enddef

    def create(self, req):
        # check if session exist
        if not self.id or not req.mc.get(self.id):
            self.id = sha("%s" % time()).hexdigest()
            # bad session (probably expired)
            while not req.mc.add(self.id, {}, time = self.expires):
                if len(req.mc.get_stats()) == 0:
                    raise RuntimeError('Memmcached server not connect!')
                self.id = sha("%s" % time()).hexdigest()
            #endwhile
        #endif

        return self.id
    #enddef

    def read(self, req):
        return req.mc.get(self.id)
    #enddef

    def write(self, req, data):
        return req.mc.replace(self.id, data, time = self.expires)
    #enddef

    def clean(self, req):
        return req.mc.delete(self.id)
    #enddef

#endclass

# TODO: not available now
class FileSession(Session):
    """
    File session. Data are stored in filesystem in tmp.
    """
    def __init__(self, req, expires = 60*60, path = '/', SID = 'SESSID'):
        raise NotImplementedError('FileSession class is not implemented yet.')
        #Session.__init__(self, req, expires, path, SID)
    #enddef

    def create(self, req):
        pass
    #enddef

    def read(self, req):
        pass
    #enddef

    def write(self, req, data):
        pass
    #enddef

    def clean(self, req):
        pass
    #enddef

#endclass
