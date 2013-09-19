#!/usr/bin/python

from distutils.core import setup
from os import path, makedirs
from shutil import copyfile

if not path.exists('build/_scripts_'):
    makedirs('build/_scripts_')
copyfile('poorhttp.py', 'build/_scripts_/poorhttp')

setup(
    name                = "poorhttp",
    version             = "20120305",
    description         = "Poor Http server for Python",
    author              = "Ondrej Tuma",
    author_email        = "mcbig@zeropage.cz",
    url                 = "http://poorhttp.zeropage.cz/",
    packages            = ['poorhttp'],
    scripts             = ['build/_scripts_/poorhttp'],
    data_files          = [('/etc/init.d', ['init.d/poorhttp']),
                           ('/etc', ['etc/poorhttp.ini']),
                           ('/srv/app', ['simple.py']),
                           ('/var/run', []), ('/var/log', []),
                           ('share/doc/poorhttp', ['doc/index.html'])],
    license             = "BSD",
    long_description    =
            """
            Poor Http Server is standalone wsgi/http server, which is designed
            for using python web applications. Unlike other projects, this is
            not framework, but single server type application. It is not
            depended on another special technologies or frameworks, only on base
            python library.
            """,
    classifiers         = [
            "Development Status :: 4 - Beta",
            "Environment :: No Input/Output (Daemon)",
            "Intended Audience :: Customer Service",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: BSD License",
            "Natural Language :: English",
            "Natural Language :: Czech",
            "Natural Language :: English",
            "Programming Language :: Python :: 2",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Server",
    ],
)
