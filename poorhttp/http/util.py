# $Id$
#

from getopt import getopt
from exceptions import OSError

import sys, os

from classes import Log, ForkingServer, ThreadingServer

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
    # set default values
    env.cfg.add_section('http')                 # http section
    env.cfg.set('http', 'webmaster', 'root@localhost')
    env.cfg.set('http', 'errorlog', '/var/log/poorhttp-error.log')
    env.cfg.set('http', 'accesslog', '/var/log/poorhttp-access.log')
    env.cfg.set('http', 'document', '/srv/www')
    env.cfg.set('http', 'index', 'False')
    env.cfg.set('http', 'type', 'single')
    env.cfg.set('http', 'application', '')
    env.cfg.set('http', 'path', './')
    env.cfg.set('http', 'autoreload', 'False')
    env.cfg.set('http', 'optimize', '1')

    env.cfg.add_section('poor')                 # poor section
    env.cfg.set('poor', 'debug', 'False')
    env.cfg.set('poor', 'loglevel', 'warn')
    env.cfg.set('poor', 'buffersize', '4096')
    env.cfg.set('poor', 'secretkey', '$Id$')

    env.cfg.add_section('mime-type')            # mime-type section
    # no default mime-types defined

    env.cfg.add_section('environ')              # environ section
    # no default application environment defined

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
            # couse default values for these variables is not good idea
        #endif
    else:
        env.cfg.read(opts['config'])
    #endif

    # some http variable could be set from command line
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

    # set environment from cfg
    if env.cfg.has_option('http', 'webmaster'):
        os.environ['SERVER_ADMIN'] = env.cfg.get('http', 'webmaster')
    if env.cfg.has_option('http', 'document'):
        document_root = env.cfg.get('http', 'document')
        os.environ['DOCUMENT_ROOT'] = os.path.abspath(document_root)
    if env.cfg.has_option('http', 'index'):
        os.environ['poor.DocumentIndex'] = env.cfg.get('http', 'index')

    if env.cfg.has_option('http', 'type'):
        server_type = env.cfg.get('http', 'type')
        if server_type == "forking":
            env.server_class = ForkingServer
        elif server_type == "threading":
            env.server_class = ThreadingServer
        os.environ['poor.ServerType'] = server_type
    if env.cfg.has_option('http', 'path'):
        python_paths = env.cfg.get('http', 'path', './').split(':')
        python_paths.reverse()
        for path in python_paths:
            sys.path.insert(0, os.path.abspath(path))
        #endfor
    if env.cfg.has_option('http', 'application'):
        appfile = env.cfg.get('http', 'application')
        if not os.access(appfile, os.R_OK) or not os.path.isfile(appfile):
            usage('Access denied to %s' % appfile)
        os.environ['poor.Application'] = os.path.splitext(os.path.basename(appfile))[0]
        sys.path.insert(0, os.path.abspath(os.path.dirname(appfile)))
    if env.cfg.has_option('http', 'autoreload'):
        os.environ['poor.AutoReload'] = env.cfg.get('http', 'autoreload')
    if env.cfg.has_option('http', 'optimze'):
        os.environ['poor.Optimze'] = env.cfg.get('http', 'index')
    #endif

    # poor section
    if env.cfg.has_option('poor', 'debug'):
        os.environ['poor_Debug'] = env.cfg.get('poor', 'debug')
    if env.cfg.has_option('poor', 'loglevel'):
        os.environ['poor_LogLevel'] = env.cfg.get('poor', 'loglevel')
    if env.cfg.has_option('poor', 'buffersize'):
        os.environ['poor_BufferSize'] = env.cfg.get('poor', 'buffersize')
    if env.cfg.has_option('poor', 'secretkey'):
        os.environ['poor_SecretKey'] = env.cfg.get('poor', 'secretkey')
    
    # application environment
    for option in env.cfg.options('environ'):
        os.environ[option] = env.cfg.get('environ', option)
        env.log.error('set %s to %s' % (option, os.environ[option]))
    #endfor

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
