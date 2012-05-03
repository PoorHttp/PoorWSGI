#
# $Id$
#
## \namespace session
#  Cookie sessions.

from Cookie import SimpleCookie
from hashlib import sha1
from time import time
from pickle import dumps, loads
from base64 import b64decode, b64encode
from exceptions import NotImplementedError
from types import DictType

import bz2

## \defgroup api Poor Application Interface
# @{

def hidden(text, passwd):
    """(en|de)crypt text with sha hash of passwd via xor.
    @param  text    raw data to (en|de)crypt
    @param  passwd  password
    @returns string
    """
    
    passwd = sha1(passwd).digest()
    passlen = len(passwd)
    retval = ''
    for i in xrange(len(text)):
        retval += chr(ord(text[i]) ^ ord(passwd[i % passlen]))
    return retval
#enddef

class PoorSession:
    """Self-contained cookie with session data"""

    def __init__(self, req, expires = 0, path = '/', SID = 'SESSID'):
        """Constructor.
        @param  req     mod_python.apache.request
        @param  expires cookie expire time in seconds, if it 0, no expire is set
        @param  path    cookie path
        @param  SID     cookie key name
        """

        # @cond PRIVATE
        self.SID = SID
        self.expires = expires
        self.path = path
        self.cookie = SimpleCookie()
        # @endcond

        ## @property data
        # data is session dictionary to store user data in cookie
        self.data = {}

        raw = None

        # get SID from cookie
        if req.subprocess_env.has_key("HTTP_COOKIE"):
            self.cookie.load(req.subprocess_env["HTTP_COOKIE"])
            if self.cookie.has_key(SID):
                raw = self.cookie[SID].value
        #endif

        if raw:
            try:
                self.data = loads(hidden(bz2.decompress(b64decode(raw)),
                                    req.secretkey))
                if type(self.data) != DictType:
                    raise RuntimeError()
            except:
                req.log_error('Bad session data.')
            #endtry

            if 'expires' in self.data and self.data['expires'] < int(time()):
                req.log.error('I: Session was expired, generating new.')
                self.data = {}
            #endif
        #endif

    #enddef

    def renew(self):
        """Renew cookie, in fact set expires to next time if it set."""
        if self.expires:
            self.data['expires'] = int(time()) + self.expires
            return

        if 'expires' in self.data:
            self.data.pop('expires')
    #enddef

    def write(self, req):
        """Store data to cookie value. This method is called automaticly in
        header method.
        @param req http.classes.Request
        """
        raw = b64encode(bz2.compress(hidden(dumps(self.data),
                                     req.secretkey), 9))
        self.cookie[self.SID] = raw
        self.cookie[self.SID]['path'] = self.path

        if self.expires:
            self.data['expires'] = int(time()) + self.expires
            self.cookie[self.SID]['expires'] = self.expires
            
        return raw
    #enddef

    def destroy(self):
        """Destroy session. In fact, set cookie expires value to past (-1)."""
        self.data = {}
        self.data['expires'] = -1
        self.cookie[self.SID]['expires'] = -1
    #enddef

    def header(self, req, headers_out = None):
        """Generate cookie headers and append it to headers_out if it set.
        @param req http.classes.Request
        @param headers_out http.classes.Headers object
        @returns list of cookie header pairs
        """
        self.write(req)
        cookies = self.cookie.output().split('\r\n')
        header = []
        for cookie in cookies:
            var = cookie[:10] # Set-Cookie
            val = cookie[12:] # SID=###; expires=###; Path=/
            header.append((var,val))
            if headers_out:
                headers_out.add(var, val)
        return header
    #enddef
#endclass

class Session:
    """
    Base Session self-contained class, data are store to DATA variable in cookie.
    """
    def __init__(self, req, expires = 60*60, path = '/', SID = 'SESSID',
                                                         DATA = '_DATA'):
        """Constructor.
        @param  req     http.classes.Request
        @param  expires cookie expire time in seconds, if it 0, no expire is set
        @param  path    cookie path
        @param  SID     cookie key name
        @param  DATA    cookie data name
        """

        # @cond PRIVATE
        self.SID = SID
        self.DATA = DATA
        self.id = None
        self.expires = expires
        self.cookie = SimpleCookie()
        # @endcond

        # get SID from cookie or url
        if req.subprocess_env.has.key("HTTP_COOKIE"):
            self.cookie.load(req.subprocess_env["HTTP_COOKIE"])
            if self.cookie.has_key(SID):
                self.id = self.cookie[SID].value
        #endif

        self.create(req)

        # complete cookie
        self.cookie[SID] = self.id
        self.cookie[SID]['path'] = path
        self.cookie[SID]['expires'] = expires
    #enddef

    
    def create(self, req):
        """Load session if exist or create new.
        @private This method is called inetrnaly.
        http.classes.Request
        """
        if self.id:
            try:
                date_expires = int(hidden(b64decode(self.id),
                                          server_secret + req.user_agent))
            except:
                req.log.error('Bad session ID `%s`.' % self.id)
                date_expires = 0
                self.id = None
            #endtry
            if date_expires < int(time()) and self.id:
                req.log.error('I: Session was expired, generating new.')
                self.id = None
            #endif
        #endif

        if not self.id:
            date_expires = int(time()) + self.expires
            self.id = b64encode(hidden(str(date_expires),
                                       server_secret + req.user_agent))
            self.cookie.clear()
        return self.id
    #enddef

    def renew(self):
        """Renew cookie, in fact set expires to next time if it set.
        @returns id integer
        """
        if self.expires:
            date_expires = int(time()) + self.expires
            self.id = b64encode(hidden(str(date_expires),
                            server_secret + req.user_agent))

        if 'expires' in self.data:
            self.data.pop('expires')

        return self.id
    #enddef


    def read(self, req):
        """Reads data from cookie.
        @param req http.classes.Request object
        @returns data or empty dictionary if fails or not exists
        """
        if self.cookie.has_key(self.DATA):
            b64 = self.cookie[self.DATA].value
            try:
                data = loads(hidden(bz2.decompress(b64decode(b64)),
                                    server_secret + self.id))
            except:
                req.log.error('Error when reading cookie data: %s' % b64,
                              req.remote_host)
                data = {}
        else:
            data = {}
        return data
    #enddef

    def write(self, req, data):
        """ Write data to cookie.
        @param req http.classes.Request object
        @param data any type data
        """
        b64 = b64encode(bz2.compress(hidden(dumps(data),
                                     server_secret + self.id), 9))
        self.cookie[self.DATA] = b64
        self.cookie[self.DATA]['expires'] = self.expires
        return True
    #enddef

    def clean(self, req):
        """Clean session data (set to empty dictionary). In fact, set cookie
        DATA expires value to past (-1). This method does not destroy session.
        @param req http.classes.Request object
        """
        b64 = b64encode(bz2.compress(hidden(dumps({}),
                                     server_secret + self.id), 9))
        self.cookie[self.DATA] = b64
        self.cookie[self.DATA]['expires'] = -1
        return True
    #enddef

    def destroy(self, req):
        """Destroy session. In fact, set cookie expires value to past (-1).
        @param req http.classes.Request object
        """
        self.clean(req)
        self.cookie[self.SID]['expires'] = -1
    #enddef

    def header(self, req, headers_out = None):
        """Generate cookie headers and append it to headers_out if it set.
        @param req http.classes.Request object
        @param headers_out http.classes.Headers object
        @returns list of cookie header pairs
        """
        cookies = self.cookie.output().split('\r\n')
        header = []
        for cookie in cookies:
            var = cookie[:10] # Set-Cookie
            val = cookie[12:] # SID=###; expires=###; Path=/
            header.append((var,val))
            if headers_out:
                headers_out.add(var, val)
        return header
    #enddef

#endclass

class MCSession(Session):
    """
    Memcache session, data are stored to memcache server
    """
    def __init__(self, req, expires = 60*60, path = '/', SID = 'SESSID'):
        """Constructor.
        @param  req     http.classes.Request
        @param  expires cookie expire time in seconds, if it 0, no expire is set
        @param  path    cookie path
        @param  SID     cookie key name
        """
        Session.__init__(self, req, expires, path, SID)
    #enddef

    def create(self, req):
        # check if session exist
        if not self.id or not req.mc.get(self.id):
            self.id = sha1("%s" % time()).hexdigest()
            # bad session (probably expired)
            while not req.mc.add(self.id, {}, time = self.expires):
                if len(req.mc.get_stats()) == 0:
                    raise RuntimeError('Memmcached server not connect!')
                self.id = sha1("%s" % time()).hexdigest()
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

class FileSession(Session):
    """
    File session, data are stored in filesystem in tmp.
    \b Warning: This session is not implemented yet !"""

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

## @}
