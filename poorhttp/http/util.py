
from getopt import getopt
from exceptions import OSError
from re import compile
from cgi import FieldStorage as CgiFieldStorage, parse_header 

import sys, os

from classes import Log, ForkingServer, ThreadingServer, Request

import env

def usage(err = None):
    """ """
    o = sys.stderr if err else sys.stdout

    o.write("Poor http - python web server\n")
    
    if err:
        o.write(
            "Error:\n"
            "     %s\n\n" % err
        )
    #endif
        
    o.write(
        "Usage: \n"
        "     poorhttp [options]\n\n"
        "Options:\n"
        "     -h, --help                        only print this help text\n"
        "     -v, --version                     only print server version\n"
        "\n"
        "     --config=/etc/poorhttp.ini        config file, default ./poorhttp.ini\n"
        "     --pidfile=/var/run/poorhttp.pid   pid file, by default gets from config\n"
        "     --address=127.0.0.1               listening address, by default gets from\n"
        "                                       config\n"
        "     --port=8080                       listening port, by default gets from\n"
        "                                       config\n"
    )

    if err:
        sys.exit(1)
#enddef
    
def configure():
    (pairs, endval) = getopt(
                sys.argv[1:],
                'hv',
                ['config=', 'pidfile=', 'address=', 'port=', 'help', 'version']
            )

    opts = {'config': './poorhttp.ini'}
    for var, val in pairs:
        opts[var[2:]] = val
        if var in ('--help', '-h'):
            usage()
            sys.exit(0)

        if var in ('--version', '-v'):
            sys.stdout.write("Poor Http Server version %s.\n" \
                    % env.server_version);
            sys.exit(0)
    #endfor

    if not os.access(opts['config'], os.F_OK):
        if not 'pidfile' in opts or not 'address' in opts or not 'port' in opts:
            usage('config file not readable!')
        #endif

        env.cfg.add_section('http')
    else:
        env.cfg.read(opts['config'])
    #endif

    for key, val in opts.items():
        env.cfg.set('http', key, val)
    #endfor

    if not env.cfg.has_option('http','pidfile'):
        usage('pidfile not configure!')
    if not env.cfg.has_option('http','address'):
        usage('address not configure!')
    if not env.cfg.has_option('http','port'):
        usage('port not configure!')
    #endif

    try:
        env.log = Log(env.cfg)
    except OSError, e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    #endtry

    # cofigure additionals
    if env.cfg.has_option('http', 'type'):
        server_type = env.cfg.get('http', 'type')
        if server_type == "forking":
            env.server_class = ForkingServer
        elif server_type == "threading":
            env.server_class = ThreadingServer
    
    if env.cfg.has_option('http', 'secretkey'):
        env.secretkey = env.cfg.get('http', 'secretkey')
    if env.cfg.has_option('http', 'webmaster'):
        env.webmaster = env.cfg.get('http', 'webmaster')
    if env.cfg.has_option('http', 'application'):
        env.application = env.cfg.get('http', 'application')
    if env.cfg.has_option('http', 'document'):
        document_root = env.cfg.get('http', 'document')
        env.document_root = os.path.abspath(document_root)
    if env.cfg.has_option('http', 'index'):
        env.document_index = env.cfg.getboolean('http', 'index')
    if env.cfg.has_option('http', 'debug'):
        env.debug = env.cfg.getboolean('http', 'debug')
    if env.cfg.has_option('http', 'autoreload'):
        env.autoreload = env.cfg.getboolean('http', 'autoreload')
    #endif

    # swhitch curent dir to server path (./ default)
    env.server_path = os.getcwd()
    sys.path.insert(0, os.path.abspath(env.application))
    #sys.path.insert(0, env.server_path)
    os.chdir(env.application)

    return env.cfg
#enddef

def save_pid():
    pidfile = env.cfg.get('http', 'pidfile')
    if pidfile[0:1] != '/':
        pidfile = '%s/%s' % (env.server_path, pidfile)
    if not os.access(pidfile, os.F_OK):
        fpid = os.open(pidfile, os.O_CREAT | os.O_WRONLY, 0644)
        os.write(fpid, str(os.getpid()))
        os.close(fpid)
    else:
        usage('Pidfile %s exist!' % pidfile)
        sys.exit(1)
    #endif
    return pidfile
#enddef

class FieldStorage(CgiFieldStorage):
    def __init__(self, fp_or_req = None,
                        headers = None,
                        outerboundary = '',
                        environ = os.environ,
                        keep_blank_values = 0, 
                        strict_parsing = 0,
                        file_callback = None,
                        field_callback = None):
        
        self.environ = environ
        req = None
        if fp_or_req and isinstance(fp_or_req, Request):
            req = fp_or_req
            fp_or_req = None
            environ = req.environ

        if file_callback:
            environ['wsgi.file_callback'] = file_callback

        if req and req.method == 'POST':
            fp_or_req = environ.get('wsgi.input')
            
        CgiFieldStorage.__init__(
                    self,
                    fp = fp_or_req,
                    headers = headers,
                    outerboundary = outerboundary,
                    environ = environ,
                    keep_blank_values = keep_blank_values,
                    strict_parsing = strict_parsing)
    #enddef

    def make_file(self, binary = None):
        if 'wsgi.file_callback' in self.environ:
            return self.environ['wsgi.file_callback'](self.filename)
        else:
            return CgiFieldStorage.make_file(self, binary)
    #enddef

    def getfirst(self, name, default = None, fce = None):
        if fce:
            return fce(CgiFieldStorage.getfirst(self, name, default))
        return CgiFieldStorage.getfirst(self, name, default)
    #enddef
#endclass
