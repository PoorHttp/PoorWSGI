"""PoorSession self-contained cookie class.

:Classes:   NoCompress, PoorSession
:Functions: hidden
"""
from hashlib import sha512
from time import time
from pickle import dumps, loads
from base64 import b64decode, b64encode

import bz2
import logging as log

from http.cookies import SimpleCookie


def hidden(text, passwd):
    """(en|de)crypt text with sha hash of passwd via xor.

    Arguments:
        text : str
            raw data to (en|de)crypt. Could be str, or bytes
        passwd : str
            password
    """
    if isinstance(passwd, bytes):
        passwd = sha512(passwd).digest()
    else:
        passwd = sha512(passwd.encode("utf-8")).digest()
    passlen = len(passwd)

    # text must be bytes
    if isinstance(text, str):
        text = text.encode("utf-8")

    if isinstance(text, str):       # text is str, we are in python 2.x
        retval = ''
        for i in range(len(text)):
            retval += chr(ord(text[i]) ^ ord(passwd[i % passlen]))
    else:                           # text is bytes, we are in python 3.x
        retval = bytearray()
        for i in range(len(text)):
            retval.append(text[i] ^ passwd[i % passlen])

    return retval
# enddef


class NoCompress:
    """Fake compress class/module whith two static method for PoorSession.

    If compress parameter is None, this class is use
    """

    @staticmethod
    def compress(data, compresslevel=0):
        """Get two params, data, and compresslevel. Method only return data."""
        return data

    @staticmethod
    def decompress(data):
        """Get one parameter data, which returns."""
        return data


class PoorSession:
    """Self-contained cookie with session data.

    You cat store or read data from object via PoorSession.data variable which
    must be dictionary. Data is stored to cookie by pickle dump. Be careful
    with stored object. You can add object with litle python trick:

    .. code:: python

        sess = PoorSession(req)

        sess.data['class'] = obj.__class__          # write to cookie
        sess.data['dict'] = obj.__dict__.copy()

        obj = sess.data['class']()                  # read from cookie
        obj.__dict__ = sess.data['dict'].copy()

    Or for beter solution, you can create export and import methods for you
    object like that:

    .. code:: python

        class Obj(object):
            def import(self, d):
                self.attr1 = d['attr1']
                self.attr2 = d['attr2']

            def export(self):
                d = {'attr1': self.attr1, 'attr2': self.attr2}
                return d

        obj = Obj()
        sess = PoorSession(req)

        sess.data['class'] = obj.__class__          # write to cookie
        sess.data['dict'] = obj.export()

        obj = sess.data['class']()                  # read from cookie
        obj.import(sess.data['dict'])
    """

    def __init__(self, req, expires=0, path='/', SID='SESSID', compress=bz2):
        """Constructor.

        Arguments:
            expires : int
                cookie expire time in seconds, if it 0, no expire is set
            path : str
                cookie path
            SID : str
                cookie key name
            compress : compress module or class.
                Could be bz2, gzip.zlib, or any other, which have standard
                compress and decompress methods. Or it could be None to not use
                any compressing method.
        """
        if req.secret_key is None:
            raise RuntimeError("poor_SecretKey is not set!")

        self.__secret_key = req.secret_key
        self.__SID = SID
        self.__expires = expires
        self.__path = path
        self.__cps = compress if compress is not None else NoCompress

        # data is session dictionary to store user data in cookie
        self.data = {}
        self.cookie = SimpleCookie()
        self.cookie[SID] = None

        raw = None

        if req.cookies and SID in req.cookies:
            raw = req.cookies[SID].value

        if raw:
            try:
                self.data = loads(hidden(self.__cps.decompress
                                         (b64decode(raw.encode())),
                                         self.__secret_key))
                if not isinstance(self.data, dict):
                    raise RuntimeError()
            except Exception as err:
                log.info(err.__repr__())
                log.warning('Bad session data.')

            if 'expires' in self.data and self.data['expires'] < int(time()):
                log.info('Session was expired, generating new.')
                self.data = {}
    # enddef

    def renew(self):
        """Renew cookie, in fact set expires to next time if it set."""
        if self.__expires:
            self.data['expires'] = int(time()) + self.__expires
            return

        if 'expires' in self.data:
            self.data.pop('expires')

    def write(self):
        """Store data to cookie value.

        This method is called automatically in header method.
        """
        raw = b64encode(self.__cps.compress(hidden(dumps(self.data),
                                                   self.__secret_key), 9))
        raw = raw if isinstance(raw, str) else raw.decode()
        self.cookie[self.__SID] = raw
        self.cookie[self.__SID]['path'] = self.__path

        if self.__expires:
            self.data['expires'] = int(time()) + self.__expires
            self.cookie[self.__SID]['expires'] = self.__expires

        return raw
    # enddef

    def destroy(self):
        """Destroy session. In fact, set cookie expires value to past (-1)."""
        self.data = {}
        self.data['expires'] = -1
        self.cookie[self.__SID]['expires'] = -1

    def header(self, headers=None):
        """Generate cookie headers and append it to headers if it set.

        Returns list of cookie header pairs.

            **headers** headers is Headers or Response object, which is used
                        to write header directly.
        """
        self.write()
        cookies = self.cookie.output().split('\r\n')
        retval = []
        for cookie in cookies:
            var = cookie[:10]   # Set-Cookie
            val = cookie[12:]   # SID=###; expires=###; Path=/
            retval.append((var, val))
            if headers:
                headers.add_header(var, val)
        return retval
    # endclass
