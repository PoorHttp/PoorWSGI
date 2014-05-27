"""
Poor WSGI for Python is light WGI connector with uri routing between WSGI server
and your application.
"""
from distutils.core import setup
from distutils.command.build import build
from distutils.command.clean import clean
from distutils.dir_util import remove_tree
from distutils import log

from os import path, makedirs, walk, environ
from shutil import copyfile
from subprocess import call
from sys import version_info

if version_info[0] >= 3:
    from io import FileIO
    file = FileIO

from poorwsgi.state import __version__
environ.update({'PYTHONPATH': 'poorwsgi'})

def find_data_files (directory, targetFolder=""):
    rv = []
    for root, dirs, files in walk(directory):
        if targetFolder:
            rv.append (( targetFolder, list(root+'/'+f for f in files if f[0]!='.' and f[-1]!='~') ))
        else:   
            rv.append (( root, list(root+'/'+f for f in files if f[0]!='.' and f[-1]!='~') ))
    log.info(str(rv))
    return rv

class X_build(build):
    def run(self):
        log.info("creating documentation")
        if not path.exists('build/_html_'):
            makedirs('build/_html_')
        if call(['jinja24doc', '-v','_poorwsgi.html', 'doc'], 
                        stdout=file('build/_html_/index.html', 'w')):
            raise IOError(1, 'jinja24doc failed')
        if call(['jinja24doc', '-v','_poorwsgi_api.html', 'doc'],
                        stdout=file('build/_html_/api.html', 'w')):
            raise IOError(1, 'jinja24doc failed')
        if call(['jinja24doc', '-v', '_licence.html', 'doc'],
                        stdout=file('build/_html_/licence.html', 'w')):
            raise IOError(1, 'jinja24doc failed')
        copyfile('doc/style.css', 'build/_html_/style.css')
        build.run(self)             # run original build

class X_clean(clean):
    def run(self):
        for directory in ('build/_html_',):
            if path.exists(directory):
                remove_tree(directory, dry_run=self.dry_run)
            else:
                log.warn("'%s' does not exist -- can't clean it",
                            directory)
        clean.run(self)


def _setup(**kwargs):
    if version_info[0] == 2 and version_info[1] < 7:
        kwargs['install_requires'] = ['ordereddict >= 1.1']
    setup(**kwargs)


_setup(
    name                = "PoorWSGI",
    version             = __version__,
    description         = "Poor WSGI connector for Python",
    author              = "Ondrej Tuma",
    author_email        = "mcbig@zeropage.cz",
    url                 = "http://poorhttp.zeropage.cz/poorwsgi.html",
    packages            = ['poorwsgi'],
    data_files          = [
            ('share/doc/poorwsgi',
                        ['doc/ChangeLog', 'doc/licence.txt', 'doc/readme.txt']),
            ('share/poorwsgi/example',
                        ['simple.py']) ] +
            find_data_files("build/_html_", 'share/doc/poorwsgi/html'),
    license             = "BSD",
    long_description    = __doc__.strip(),
    classifiers         = [
            "Development Status :: 4 - Beta",
            "Environment :: Web Environment",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: BSD License",
            "Natural Language :: English",
            "Natural Language :: Czech",
            "Operating System :: POSIX",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 3",
            "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
            "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    build_requires      = ['jinja24doc >= 1.1.0'],
    cmdclass            = {'build': X_build,
                           'clean': X_clean },
)
