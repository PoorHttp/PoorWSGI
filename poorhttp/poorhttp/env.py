"""
    Poor Http Server Environment

    It is use for sharing variables from config and log object and
    for server request environment addons.
"""

# server type
server_class = None

# poor http version
server_version = 20120305

# server address
server_address = None

# server port
server_port = None

# server host
server_host = None

# user id
uid = 0

# group id
gid = 0

# global configuration
cfg = None

# log object
log = None

# debug
debug = False

# server / request environment
environ = {}

__version__ = server_version
__author__  = "Ondrej Tuma (McBig) <mcbig@zeropage.cz>"
__date__    = "19 September 2013"
