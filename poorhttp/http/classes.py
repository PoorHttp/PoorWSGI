#
# $Id$
#

from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, ServerHandler
from wsgiref.headers import Headers as WHeaders
from SocketServer import ForkingMixIn, ThreadingMixIn
from time import strftime
from os import name as osname
from types import FunctionType, MethodType
from ConfigParser import ConfigParser
from sys import exc_info
from traceback import format_exception
from httplib import responses

import os, re

from enums import *
import env, handlers

_httpUrlPatern = re.compile(r"^(http|https):\/\/")

class PoorServer(WSGIServer):
    type = "Single"
    def handle_error(self, request, client_address):
        env.log.error(exc_info(), client_address[0])

class ForkingServer(ForkingMixIn, PoorServer):
    type = "Forking"
class ThreadingServer(ThreadingMixIn, PoorServer):
    type = "Threading"

class WebRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        env.log.access(
                env.server_host,
                self.address_string(),
                self.log_date_time_string(),
                format%args)
        #WSGIRequestHandler.log_message(self, format, *args)

    def log_request(self, code='-', size='-'):
        WSGIRequestHandler.log_request(self, code, size)

    def log_error(self, *args):
        env.log.error(args, self.address_string())
        #WSGIRequestHandler.log_error(self, *args)

    def handle(self):
        """Handle a single HTTP request"""

        self.raw_requestline = self.rfile.readline()
        if not self.parse_request(): # An error code has been sent, just exit
            env.log.error(
                "[S] An error code has been sent. (WebRequestHandler.handle)")
            return

        handler = PoorServerHandler(
            self.rfile, self.wfile, self.get_stderr(), self.get_environ()
        )
        handler.request_handler = self      # backpointer for logging
        handler.run(self.server.get_app(), self)
        
#endclass

class PoorServerHandler(ServerHandler):
    def run(self, application, request_object):
        """Invoke the application"""
        # Note to self: don't move the close()!  Asynchronous servers shouldn't
        # call close() from finish_response(), so if you close() anywhere but
        # the double-error branch here, you'll break asynchronous servers by
        # prematurely closing.  Async servers must return from 'run()' without
        # closing if there might still be output to iterate over.
        try:
            self.setup_environ()
            self.result = application(self, request_object)
            #self.result = application(self.environ, self.start_response)
            self.finish_response()
        except:
            try:
                env.log.error("[S] Application run error. (PoorServerHandler.run")
                self.handle_error()
            except:
                # If we get an error handling an error, just give up already!
                self.close()
                raise   # ...and let the actual server figure it out.
    #enddef

    def log_exception(self, exc_info):
        traceback = format_exception(exc_info[0],
                                    exc_info[1],
                                    exc_info[2])
        traceback = ''.join(traceback)
        env.log.error(traceback)
        exc_info = None
    #enddef
#endclass


class Buffer(list):
    strlen = 0

    def append(self, var):
        list.append(self,var)
        strlen += len(var)

## \defgroup http http server inetrface
# @{
#  Compatible as soon as posible with mod_python apache inteface.

class Headers(WHeaders):
    """Class inherited from wsgiref.headers.Headers."""
    
    def __init__(self):
        """By default constains Server and X-Powered-By values."""
        headers = [
            ("Server", "Poor Http (%s)" % osname),
            ("X-Powered-By", "Python")
        ]
        WHeaders.__init__(self, headers)
    
    ## TODO: mod_python.apache.Table object allows duplicite keys for cookies.
    def add(self, key, value):
        """Set header key to value. Duplicate keys are not allowed."""
        if self.has_key(key):
            raise KeyError("Key %s exist." % key)
        self.__setitem__(key, value)
#endclass

class Request:
    """HTTP request object with all server elements. It could be compatible
        as soon as posible with mod_python.apache.request."""

    def __init__(self, server_handler, request_object):
        #apache compatibility

        self.environ = server_handler.environ

        ## A table object containing environment information typically usable
        #  for CGI.
        self.subprocess_env = self.environ

        ## String. Host, as set by full URI or Host: header.
        self.hostname = self.environ.get('HTTP_HOST')

        ## A string containing the method - 'GET', 'HEAD', 'POST', etc. Same as
        #  CGI REQUEST_METHOD
        self.method = self.environ.get('REQUEST_METHOD')

        ## The path portion of the URI.
        self.uri = self.environ.get('PATH_INFO')

        ## String. The content type. Another way to set content_type is via
        #  headers_out object property.
        self.content_type = None

        ## Status. One of http.enums.HTTP_* values.
        self.status = 200

        ## A table object containing headers sent by the client.
        self.headers_in = request_object.headers

        ## A Headers object representing the headers to be sent to the client.
        self.headers_out = Headers()

        ## These headers get send with the error response, instead of headers_out.
        self.err_headers_out = Headers()
        #self.buffer = None

        ## String, which is used to encrypt http.session.PoorSession and
        #  http.session.Session
        self.secretkey = env.secretkey

        # @cond PRIVATE
        self.start_response = server_handler.start_response
        self._start_response = False
        

        self.remote_host = self.environ.get('REMOTE_HOST')
        self.remote_addr = self.environ.get('REMOTE_ADDR')
        self.user_agent = self.environ.get('HTTP_USER_AGENT')
        self.scheme = self.environ.get('wsgi.url_scheme')
        # @endcond
    #enddef
    
    def _write(self, data):
        data = str(data)
        #self.buffer.append(data)
        #if self.buffer.strlen > 2048:
        self.__write(data)

    def write(self, data):
        """
        At firts call this function internal start_response will be call,
        headers_out are send, and then data will be writen.
        Next call only write data.
        """
        if self.content_type and not self.headers_out.get('Content-Type'):
            self.headers_out.add('Content-Type', self.content_type)

        self.__write = self.start_response(
                            "%d %s" % (self.status, responses[self.status]), 
                            self.headers_out.items())
        self.write = self._write
        self._start_response = True
        #self.buffer = Buffer()
        self.write(data)
    #enddef

    def add_common_vars(self):
        """only set \b REQUEST_URI"""
        self.subprocess_env['REQUEST_URI'] = environ.get('PATH_INFO')

    def get_options(self):
        """Returns a reference to the ConfigParser object containing the
        server options."""
        if not env.cfg.has_section('application'):
            return {}
        return env.cfg.__dict__['_sections']['application']

    def get_remote_host(self):
        """Returns REMOTE_ADDR CGI enviroment variable."""
        return self.remote_addr

    def document_root(self):
        """Returns DocumentRoot setting."""
        return env.document_root

    def construct_url(self, uri):
        """This function returns a fully qualified URI string from the path
        specified by uri, using the information stored in the request to
        determine the scheme, server host name and port. The port number is not
        included in the string if it is the same as the default port 80."""

        if not _httpUrlPatern.match(uri):
            return "%s://%s%s" % (self.scheme, self.hostname, uri)
        return uri
    #enddef

    def log_error(self, message, level = LOG_NOTICE, server = None):
        """An interface to the server http.classes.log.error method. 
        @param message string with the error message
        @param level is one of the following flags constants:
        \code
        LOG_EMERG
        LOG_ALERT
        LOG_CRIT
        LOG_ERR
        LOG_WARNING
        LOG_NOTICE
        LOG_INFO
        LOG_DEBUG
        LOG_NOERRNO
        \endcode
        APLOG_constains are supported too for easier migration from mod_python.
        @param server interface only compatibility parameter
        """

        if env.log_level >= level[0]:
            env.log.error("[%s] %s" % (level[1], message), self.remote_host)

    def flush(self):
        """Flushes the output buffer."""
        if not self._start_response:
            self.write('')
        return ()
    #enddef

    def sendfile(self, path, offset = 0, limit = -1 ):
        """
        Send file defined by path to client. offset and len is not supported yet
        """
        if not os.access(path, os.R_OK):
            raise IOError("Could not stat file for reading")
        
        length = 0

        bf = os.open(path, os.O_RDONLY)

        data = os.read(bf, 4096)
        while data != '':
            length = len(data)
            self.write(data)
            data = os.read(bf, 4096)
        #endwhile
        os.close(bf)

        return length
    #enddef

#endclass

## @}

class Log:
    """
    Logging class. When object is deleted, log file are closed.
    """

    def __init__(self, cfg):
        # when destructor is call, os module is not present, but we need
        # close fce.
        # @TODO pokud znak zacina pipou (|), tak otevrit rouru pres popen
        self.close = os.close
        self.errorlog = None
        self.accesslog = None
        
        if cfg.has_option('http', 'log_level'):
            env.log_level = cfg.getint('http', 'log_level')

        if cfg.has_option('http', 'errorlog'):
            self.errorlog = os.open(cfg.get('http', 'errorlog'),
                                    os.O_WRONLY | os.O_APPEND | os.O_CREAT )
        if cfg.has_option('http', 'accesslog'):
            self.accesslog = os.open(cfg.get('http', 'accesslog'),
                                    os.O_WRONLY | os.O_APPEND | os.O_CREAT )
        #endif
    #enddef

    def __del__(self):
        if self.errorlog:
            self.close(self.errorlog)
        if self.accesslog:
            self.close(self.accesslog)
    #enddef

    def error(self, message, remote_host = ''):
        if remote_host != '':
            remote_host = '[%s] ' % remote_host
        if self.errorlog:
            os.write(self.errorlog, '%s: %s%s\n' % 
                    (strftime("%Y-%m-%d %H:%M:%S"),
                     remote_host,
                     message))
    #enddef

    def access(self, address, host, logtime, message):
        if self.accesslog:
            # ip address - [time] -
            os.write(self.accesslog, '%s %s - [%s] %s\n' %
                        (address, host, logtime, message))
    #enddef

#endclass
