
from getopt import getopt
from exceptions import OSError

import sys, os

from classes import Log

import env

def usage(err = None):
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
                '',
                ['config=', 'pidfile=', 'address=', 'port=']
            )
    opts = {'config': './poorhttp.ini'}
    for var, val in pairs:
        opts[var[2:]] = val
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

    # connect memmcace if is possible
    if env.cfg.has_option('http','memcache'):
        mc_servers = env.cfg.get('http','memcache')
        mc_servers = map(lambda x: x.strip(), mc_servers.split(','))
        from memcache import Client as McClient
        env.mc = McClient(mc_servers, debug=0)
        if env.mc.get_stats() == 0:
            env.log.error("All memcache server(s) is down!")
        #endif
    #endif

    try:
        env.log = Log(env.cfg)
    except OSError, e:
        sys.stderr.write('%s\n' % e)
        sys.exit(1)
    #endtry

    # cofigure additionals
    if env.cfg.has_option('http', 'webmaster'):
        env.webmaster = env.cfg.get('http', 'webmaster')
    if env.cfg.has_option('http', 'application'):
        env.application = env.cfg.get('http', 'application')
    if env.cfg.has_option('http', 'document'):
        document = env.cfg.get('http', 'document')
        env.document = os.path.abspath(document)
    #endif

    # swhitch curent dir to server path (./ default)
    #print sys.path
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
