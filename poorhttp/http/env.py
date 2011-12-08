#
# $Id$
#

from ConfigParser import ConfigParser
from time import time
from enums import LOG_INFO
from classes import PoorServer

# server type
server_class = PoorServer

# poor http version
server_version = 20100720

# poor http servr root
server_root = './'

# server address
server_address = None

# server port
server_port = None

# server host
server_host = None

# poor http secretkey to crypting data (cookie)
secretkey = "$Id$"

# global configuration
cfg = ConfigParser()

# log object
log = None

# webmaster
webmaster = ''

# debug
debug = False

# auto reload modules
autoreload = False

# log_level
log_level = LOG_INFO[0]

# application path (python scripts)
application = './'

# document path (file documents)
document_root = None
