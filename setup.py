#!/usr/bin/python

from distutils.core import setup
from poorwsgi.state import __version__

setup(
    name                = "poorwsgi",
    version             = __version__,
    description         = "Poor WSGI connector for Python",
    author              = "Ondrej Tuma",
    author_email        = "mcbig@zeropage.cz",
    url                 = "http://poorhttp.zeropage.cz/",
    packages            = ['poorwsgi'],
)
