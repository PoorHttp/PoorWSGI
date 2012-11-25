#
# $Id$
#

from ConfigParser import ConfigParser
from time import time
from classes import PoorServer

# server type
server_class = PoorServer

# poor http version
server_version = 20120305

# server address
server_address = None

# server port
server_port = None

# server host
server_host = None

# global configuration
cfg = ConfigParser()

# log object
log = None

# debug
debug = False
