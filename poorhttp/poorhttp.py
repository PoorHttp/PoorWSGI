#!/usr/bin/python

from wsgiref.simple_server import make_server
from signal import signal, SIGTERM
from socket import error as SocketError, getfqdn
from ConfigParser import ParsingError
from traceback import format_exception

import sys, os

from poorhttp import env
from poorhttp.tools import usage, configure, save_pid
from poorhttp.classes import WebRequestHandler, PoorServerHandler

def sigterm(sig, stack = None):
    env.log.error('[S] Shotdown server signal(%s)' % sig)
    os.unlink(pidfile)
    sys.exit()
#enddef

try:
    cfg = configure()
    pidfile = save_pid()

    signal(SIGTERM, sigterm)
    
    env.server_address = cfg.get('http', 'address')
    env.server_port = cfg.getint('http', 'port')
    env.server_host = getfqdn(env.server_address)
    
    env.log.error('[S] Starting server type %s at %s:%s' \
            % (env.server_class.type, env.server_address, env.server_port))

    exec ("from %s import application" % env.environ['poor.Application']) in globals()
    httpd = make_server(env.server_address,
                        env.server_port,
                        application,
                        server_class = env.server_class,
                        handler_class = WebRequestHandler
                        )

    # try to change euid & egid
    if os.geteuid() == 0 and (env.uid != 0 or env.gid !=0):
        env.log.set_chown(env.uid, env.gid)     # chown log files
    if os.geteuid() == 0 and env.gid != 0:
        os.setegid(env.gid)                     # change group id
    if os.geteuid() == 0 and env.uid != 0:
        os.seteuid(env.uid)                     # change user id

    httpd.timeout = 0.5
    httpd.serve_forever()
except KeyboardInterrupt, e:
    env.log.error('[S] Shotdown server (keyboard interrupt)')
except SocketError, e:
    env.log.error("[S] %s" % e[1])
    sys.exit(1)
except ParsingError, e:
    # configure error
    usage("Exception: %s" % e.message)
    sys.exit(1)
except os.error, e:
    # pid error
    usage("Exception: %s" % e)
    sys.exit(1)
except Exception, e:
    traceback = format_exception(sys.exc_type,
                                 sys.exc_value,
                                 sys.exc_traceback)
    traceback = ''.join(traceback)
    usage("Exception: %s" % traceback)
    sys.exit(1)
finally:
    del(env.log)                                # close log files
    if os.geteuid() != os.getuid():             # pid file has real id owner
        os.setuid(os.getuid())
    try:
        os.unlink(pidfile)                      # unlink pidfile if exist
    except:
        pass
#endtry
