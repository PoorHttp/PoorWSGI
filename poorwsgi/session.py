"""
PoorSession self-contained cookie class

"""
from hashlib import sha1
from time import time
from pickle import dumps, loads
from base64 import b64decode, b64encode
from bz2 import compress, decompress
from sys import version_info

if version_info.major < 3:      # python 2.x
    from Cookie import SimpleCookie
else:                           # python 3.x
    from http.cookies import SimpleCookie
    xrange = range

from poorwsgi.state import __author__, __date__, __version__, LOG_INFO
from poorwsgi.request import uni

def hidden(text, passwd):
    """
    (en|de)crypt text with sha hash of passwd via xor.
        text    raw data to (en|de)crypt. Could be str, unicode or bytes
        passwd  password
        returns string
    """
    passwd = sha1(uni(passwd).encode("utf-8")).digest()
    passlen = len(passwd)
    
    # text must be str on python 2.x (like bytes in python 3.x)
    if version_info.major < 3 and isinstance(text, unicode):
        text = text.encode("utf-8")
    # text must be bytes
    elif version_info.major >= 3 and isinstance(text, str):
        text = text.encode("utf-8")

    if isinstance(text, str):       # text is str, we are in python 2.x
        retval = ''
        for i in xrange(len(text)):
            retval += chr(ord(text[i]) ^ ord(passwd[i % passlen]))
    else:                           # text is bytes, we are in python 3.x
        retval = bytearray()
        for i in xrange(len(text)):
            retval.append(text[i] ^ passwd[i % passlen])

    return retval
#enddef

class PoorSession:
    """Self-contained cookie with session data"""

    def __init__(self, req, expires = 0, path = '/', SID = 'SESSID'):
        """
        Constructor.
            req     mod_python.apache.request
            expires cookie expire time in seconds, if it 0, no expire is set
            path    cookie path
            SID     cookie key name
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
        if "HTTP_COOKIE" in req.environ:
            self.cookie.load(req.environ["HTTP_COOKIE"])
            if SID in self.cookie:
                raw = self.cookie[SID].value
        #endif

        if raw:
            try:
                self.data = loads(hidden(decompress(b64decode(raw.encode())),
                                    req.secretkey))
                if not isinstance(self.data, dict):
                    raise RuntimeError()
            except Exception as e:
                req.log_error(e, LOG_INFO)
                req.log_error('Bad session data.')
            #endtry

            if 'expires' in self.data and self.data['expires'] < int(time()):
                req.log_error('I: Session was expired, generating new.')
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
        """
        raw = b64encode(compress(hidden(dumps(self.data),
                                     req.secretkey), 9))
        raw = raw if isinstance(raw, str) else raw.decode()
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
        if self.SID in self.cookie:
            self.cookie[self.SID]['expires'] = -1
    #enddef

    def header(self, req, headers_out = None):
        """
        Generate cookie headers and append it to headers_out if it set.
            returns list of cookie header pairs
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
