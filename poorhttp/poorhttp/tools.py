"""
    Poor Http Server tools

    This library contains functions for parsing config file, creating pidfile
    and print usege help.
"""

from getopt import getopt
from ConfigParser import ConfigParser
from grp import getgrnam
from pwd import getpwnam

import sys, os

from classes import Log, ForkingServer, ThreadingServer, PoorServer

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
    env.cfg = ConfigParser()

    # set default values
    env.cfg.add_section('http')                 # http section
    env.cfg.set('http', 'port', '8080')
    env.cfg.set('http', 'address', '127.0.0.1')
    env.cfg.set('http', 'pidfile', '/var/run/poorhttp.pid')

    env.cfg.set('http', 'webmaster', 'root@localhost')
    env.cfg.set('http', 'errorlog', '/var/log/poorhttp-error.log')
    env.cfg.set('http', 'accesslog', '/var/log/poorhttp-access.log')
    env.cfg.set('http', 'type', 'single')
    env.cfg.set('http', 'path', './')
    env.cfg.set('http', 'optimize', '1')
    env.cfg.set('http', 'debug', 'False')

    env.cfg.add_section('environ')              # environ section
    # no default application environment defined

    (pairs, endval) = getopt(
                sys.argv[1:],
                'hv',
                ['config=', 'pidfile=', 'address=', 'port=', 'help', 'version']
            )

    opts = {'config': '/etc/poorhttp.ini'}
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

    if env.cfg.has_option('http', 'group'):
        group = env.cfg.get('http', 'group')
        try:
            env.gid = getgrnam(group).gr_gid
        except:
            usage("Group `%s' not found on system" % group)
    if env.cfg.has_option('http', 'user'):
        user = env.cfg.get('http', 'user')
        try:
            pw = getpwnam(user)
        except:
            usage("User `%s' not found on system" % user)
        env.uid = pw.pw_uid                                 # set user id
        env.gid = pw.pw_gid if env.gid == 0 else env.gid    # set users group id
    #endif

    try:
        env.log = Log(env.cfg)
    except OSError, e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    #endtry

    # set environment from cfg
    env.environ['SERVER_ADMIN'] = env.cfg.get('http', 'webmaster')
    server_type = env.cfg.get('http', 'type')
    if server_type == "forking":
        env.server_class = ForkingServer
    elif server_type == "threading":
        env.server_class = ThreadingServer
    else:
        env.server_class = PoorServer
    env.environ['poor.ServerType'] = server_type

    if not env.cfg.has_option('http', 'application'):
        usage('Application must be set')

    appfile = env.cfg.get('http', 'application')
    if not os.access(appfile, os.R_OK) or not os.path.isfile(appfile):
        usage('Access denied to %s' % appfile)
    env.environ['poor.Application'] = os.path.splitext(os.path.basename(appfile))[0]
    sys.path.insert(0, os.path.abspath(os.path.dirname(appfile)))
    env.log.error('[I] Inserting python path from application %s' % sys.path[0])

    # yes python path could be on the top of path just like uwsgi
    python_paths = env.cfg.get('http', 'path').split(':')
    python_paths.reverse()
    for path in python_paths:
        sys.path.insert(0, os.path.abspath(path))
        env.log.error('[I] Inserting python path from path option %s' % sys.path[0])
    #endfor

    env.environ['poor.Optimze'] = env.cfg.get('http', 'optimize')
        
    if env.cfg.get('http', 'debug').lower() in ('true', 'yes', 'on', '1'):
        env.debug = True
    env.environ['poor.Debug'] = str(env.debug)
    env.environ['poor.Version'] = str(env.server_version)
    
    # application environment
    for var in env.cfg.options('environ'):
        val = env.cfg.get('environ', var)
        env.environ[var] = val
        env.log.error('[I] Set variable %s to %s' % (var, val))
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
