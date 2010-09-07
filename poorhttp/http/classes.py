
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


import os

from enums import *
import env, handlers

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

class Headers(WHeaders):
    def __init__(self):
        headers = [
            ("Server", "Poor Http (%s)" % osname),
            ("X-Powered-By", "Python")
        ]
        WHeaders.__init__(self, headers)
    
    def add(self, key, value):
        if self.has_key(key):
            raise KeyError("Key %s exist." % key)
        self.__setitem__(key, value)
#endclass

class Buffer(list):
    strlen = 0

    def append(self, var):
        list.append(self,var)
        strlen += len(var)

class Reqeuest:
    def __init__(self, server_handler, request_object):
        """
        Reqeuest object with all server elements
        """

        #apache compatibility
        self.environ = server_handler.environ
        self.subprocess_env = self.environ
        self.hostname = self.environ.get('HTTP_HOST')
        self.method = self.environ.get('REQUEST_METHOD')
        self.uri = self.environ.get('PATH_INFO')

        self.content_type = None
        self.status = 200
        self.headers_in = request_object.headers
        self.headers_out = Headers()
        self.err_headers_out = Headers()
        #self.buffer = None

        # private
        self.start_response = server_handler.start_response
        self._start_response = False

        self.remote_host = self.environ.get('REMOTE_HOST')
        self.remote_addr = self.environ.get('REMOTE_ADDR')
        self.user_agent = self.environ.get('HTTP_USER_AGENT')
        self.scheme = self.environ.get('wsgi.url_scheme')
    #enddef
    
    def _write(self, data):
        data = str(data)
        #self.buffer.append(data)
        #if self.buffer.strlen > 2048:
        self.__write(data)

    def write(self, data):
        """
        At firts call this function start_response will be call, and then
        data will be writen. Next call only write data
        """
        if self.content_type and not 'Content-Type' in self.headers_out:
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
        self.subprocess_env['REQUEST_URI'] = environ.get('PATH_INFO')

    def get_options(self):
        if not env.cfg.has_section('application'):
            return {}
        return env.cfg.__dict__['_sections']['application']

    def get_remote_host(self):
        return self.remote_host

    def document_root(self):
        return env.document_root

    def log_error(self, message, level = LOG_NOTICE, server = None):
        if env.log_level >= level[0]:
            env.log.error("[%s] %s" % (level[1], message), self.remote_host)

    def flush(self):
        if not self._start_response:
            self.write('')
        return ()
    #enddef

    def sendfile(self, path):
        handlers.sendfile(self, path)
#endclass

class Log:
    """
    Logging class. When object is deleted, log file are closed.
    """

    def __init__(self, cfg):
        # when destructor is call, os module is not present, but we need
        # close fce
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
