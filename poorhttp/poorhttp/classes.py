"""
    Poor Http Server Classes

    Main server classes for handling request and Log class, which works create
    logs like from Apache.
"""

from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, ServerHandler
from SocketServer import ForkingMixIn, ThreadingMixIn
from time import strftime
from sys import exc_info
from traceback import format_exception

import os

import env
from env import __version__, __author__, __date__

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
                format % args)
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
            #self.rfile, self.wfile, self.get_stderr(), self.get_environ()
            self.rfile, self.wfile, env.log, self.get_environ()
        )
        handler.request_handler = self      # backpointer for logging
        handler.run(self.server.get_app(), self)
        
#endclass

class PoorServerHandler(ServerHandler):
    
    server_software = "Poor Http (%s)" % os.name

    def add_poor_vars(self):
        self.environ.update(env.environ)

    def run(self, application, request_object):
        """Invoke the application"""
        # Note to self: don't move the close()!  Asynchronous servers shouldn't
        # call close() from finish_response(), so if you close() anywhere but
        # the double-error branch here, you'll break asynchronous servers by
        # prematurely closing.  Async servers must return from 'run()' without
        # closing if there might still be output to iterate over.
        try:
            self.setup_environ()
            self.add_poor_vars()
            self.result = application(self.environ, self.start_response)
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

    def setup_environ(self):
        ServerHandler.setup_environ(self)

    def log_exception(self, exc_info):
        traceback = format_exception(exc_info[0],
                                    exc_info[1],
                                    exc_info[2])
        traceback = ''.join(traceback)
        env.log.error(traceback)
        exc_info = None
    #enddef
#endclass

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
        
        if cfg.has_option('http', 'debug'):
            env.debug = cfg.getboolean('http', 'debug')

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

    def set_chown(self, uid, gid):
        if self.errorlog:
            os.fchown(self.errorlog, uid, gid)
        if self.accesslog:
            os.fchown(self.accesslog, uid, gid)
    #enddef

    def write(self, message):
        self.error(message)

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
