
from ConfigParser import ConfigParser
from time import time

# poor http version
server_version = 20091126

# poor http servr root
server_root = './'

# server address
server_address = None

# server port
server_port = None

# server host
server_host = None

# poor http secret_key to crypting data (cookie)
server_secret = "%s" % time()

# global configuration
cfg = ConfigParser()

# memcache clients object
mc = None

# log object
log = None

# webmaster
webmaster = ''

# application path (python scripts)
application = './'

# document path (file documents)
document = None
