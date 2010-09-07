
from wsgiref.simple_server import WSGIRequestHandler
from time import strftime

import cgi, os

import response, env

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
        
#endclass

class Reqeuest(object):
    def __init__(self, environ, start_response):
        """
        Reqeuest object with all server elements
        """
        #server env
        self.cfg = env.cfg
        self.log = env.log
        self.mc = env.mc
        self.webmaster = env.webmaster
        self.document = env.document
        self.server_version = env.server_version

        #request env
        self.environ = environ
        self.start_response = start_response
        self.path = environ.get('PATH_INFO')
        self.method = environ.get('REQUEST_METHOD')
        self.remote_addr = environ.get('REMOTE_ADDR')
        self.remote_host = environ.get('REMOTE_HOST')
        self.cookie = environ.get('HTTP_COOKIE')
        if self.method == 'GET':
            self.form = cgi.FieldStorage(environ = environ)
        elif self.method == 'POST':
            self.form = cgi.FieldStorage(fp = environ.get('wsgi.input'),
                                         environ = environ)
        else:
            self.form = None
        #endif

        # request additional
        self.NotFound = response.NotFound
        self.InternalServerError = response.InternalServerError
        self.SID = None
        self.DATA = None

        self.status = {
            200: '200 Ok',
            301: '301 Moved permanently',
            302: '302 Found',
            403: '403 Forbidden',
            404: '404 Not Found',
            500: '500 Internal Server Error',
        }
    #enddef

    def setNotFound(self, _class):
        """
        Set http 404 Not Found result. It is raise when url has no user call
        in dispatch_table. It must be subclass from response.Ok. And it must
        have one [pivinny] paramter url.
        """
        if not issubclass(_class, response.Ok):
            raise TypeError("Class %s is not subclass of response.Ok." % _class.__name__)
        self.NotFound = _class
    #enddef

    def setInternalServerError(self, _class):
        """
        Set http 500 Internal Error result. It is raise when Exception
        is catch (syntax error etc.) It must be subclass from response.Ok
        and don't have any [povinny] parametr.
        """
        if not issubclass(_class, response.Ok):
            raise TypeError("Class %s is not subclass of response.Ok." % _class.__name__)
        self.InternalServerError = _class
    #enddef

#endclass

class Log:
    """
    Logging class. When object is deleted, log file are closed.
    """

    def __init__(self, cfg):
        self.errorlog = None
        self.accesslog = None
        self.debug = 0

        if cfg.has_option('http', 'debug'):
            self.debug = cfg.getint('http', 'debug')

        if cfg.has_option('http', 'errorlog'):
            self.errorlog = os.open(cfg.get('http', 'errorlog'),
                                    os.O_WRONLY | os.O_APPEND | os.O_CREAT )
        if cfg.has_option('http', 'accesslog'):
            self.accesslog = os.open(cfg.get('http', 'accesslog'),
                                    os.O_WRONLY | os.O_APPEND | os.O_CREAT )
        #endif
    #enddef

    def __del__(self):
        # when destructor is call, os module is not present
        from os import close
        if self.errorlog:
            close(self.errorlog)
        if self.accesslog:
            close(self.accesslog)
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
