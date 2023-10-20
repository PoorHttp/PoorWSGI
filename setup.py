"""PoorWSGI setup.py"""
from distutils.command.install_data import install_data  # type: ignore
from distutils.dir_util import remove_tree

from os import path, makedirs, walk, environ
from shutil import copyfile
from subprocess import call

import logging

from setuptools import Command, setup  # type: ignore
from setuptools.command.test import test  # type: ignore

from poorwsgi.state import __version__


environ.update({'PYTHONPATH': 'poorwsgi'})


def find_data_files(directory, target_folder=""):
    """Find files in directory, and prepare tuple for setup."""
    retval = []
    for root, _, files in walk(directory):
        if target_folder:
            retval.append(
                    (target_folder,
                     list(root+'/'+f
                          for f in files if f[0] != '.' and f[-1] != '~')))
        else:
            retval.append(
                    (root,
                     list(root+'/'+f
                          for f in files if f[0] != '.' and f[-1] != '~')))
    return retval


class BuildDoc(Command):
    """Build html documentation."""
    description = "build html documentation, need jinja24doc >= 1.1.0"
    user_options = [
            ('build-base=', 'b',
             "base build directory (default: 'build.build-base')"),
            ('html-temp=', 't', "temporary documentation directory"),
            ('public', 'p', "build as part of public poorhttp web")
        ]

    def initialize_options(self):
        self.build_base = None
        self.html_temp = None
        self.public = False

    def finalize_options(self):
        self.set_undefined_options('build',
                                   ('build_base', 'build_base'))
        if self.html_temp is None:
            self.html_temp = path.join(self.build_base, 'html')

    def page(self, in_name, out_name=None):
        """Generate page."""
        if out_name is None:
            out_name = in_name
        if call(['jinja24doc', '-v', '--var', f'public={self.public}',
                 f'_{in_name}.html', 'doc'],
                stdout=open(f'{self.html_temp}/{out_name}.html', 'w',
                            encoding="utf-8")):
            raise IOError(1, 'jinja24doc failed')

    def run(self):
        logging.info("building html documentation")
        if self.public:
            logging.info("building as public part of poorhttp web")
        if self.dry_run:
            return

        if not path.exists(self.html_temp):
            makedirs(self.html_temp)
        self.page('poorwsgi', 'index')
        self.page('install')
        self.page('documentation')
        self.page('poorwsgi_api', 'api')
        self.page('licence')
        copyfile('doc/style.css', self.html_temp+'/style.css')
        copyfile('doc/web.css', self.html_temp+'/web.css')
        copyfile('doc/small-logo.png', self.html_temp+'/small-logo.png')


class CleanDoc(Command):
    """Clean temporary files from build_doc command."""
    description = "clean up temporary files from 'build_doc' command"
    user_options = [
            ('build-base=', 'b',
             "base build directory (default: 'build-html.build-base')"),
            ('html-temp=', 't',
             "temporary documentation directory")
        ]

    def initialize_options(self):
        self.build_base = None
        self.html_temp = None

    def finalize_options(self):
        self.set_undefined_options('build_doc',
                                   ('build_base', 'build_base'),
                                   ('html_temp', 'html_temp'))

    def run(self):
        if path.exists(self.html_temp):
            remove_tree(self.html_temp, dry_run=self.dry_run)
        else:
            logging.warn("'%s' does not exist -- can't clean it", self.html_temp)


class InstallDoc(install_data):
    """Install documentation files."""
    description = "install html documentation"
    user_options = install_data.user_options + [
        ('build-base=', 'b',
         "base build directory (default: 'build-html.build-base')"),
        ('html-temp=', 't',
         "temporary documentation directory"),
        ('skip-build', None, "skip the build step"),
        ]

    def initialize_options(self):
        self.build_base = None
        self.html_temp = None
        self.skip_build = None
        install_data.initialize_options(self)

    def finalize_options(self):
        self.set_undefined_options('build_doc',
                                   ('build_base', 'build_base'),
                                   ('html_temp', 'html_temp'))
        self.set_undefined_options('install',
                                   ('skip_build', 'skip_build'))
        install_data.finalize_options(self)

    def run(self):
        if not self.skip_build:
            self.run_command('build_doc')
        self.data_files = find_data_files(self.html_temp,
                                          'share/doc/poorwsgi/html')
        install_data.run(self)


class PyTest(test):
    """Run tests."""
    user_options = [('pytest-args=',
                     'a', 'Arguments to pass to py.test.'),
                    ('test-suite=',
                     't', 'Test suite/module::Class::test')]

    def initialize_options(self):
        test.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        test.finalize_options(self)
        if isinstance(self.pytest_args, (str)):
            self.pytest_args = self.pytest_args.split(' ')

        self.pytest_args.append(self.test_suite or 'tests')
        if self.verbose:
            self.pytest_args.insert(0, '-v')

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        if pytest.main(self.pytest_args) != 0:
            raise RuntimeError("Test failed")


def doc():
    """Return README.rst content."""
    with open('README.rst', 'r', encoding="utf-8") as readme:
        return readme.read().strip()


setup(
    name="PoorWSGI",
    version=__version__,
    description="Poor WSGI connector for Python",
    author="Ondřej Tůma",
    author_email="mcbig@zeropage.cz",
    maintainer="Ondrej Tuma",
    maintainer_email="mcbig@zeropage.cz",
    url="http://poorhttp.zeropage.cz/poorwsgi",
    project_urls={
        'Documentation': 'http://poorhttp.zeropage.cz/poorwsgi',
        'Funding': 'https://github.com/sponsors/ondratu',
        'Source': 'https://github.com/poorHttp/PoorWSGI',
        'Tracker': 'https://github.com/PoorHttp/PoorWSGI/issues'},
    packages=['poorwsgi'],
    package_data={'': ['py.typed']},
    data_files=[
        ('share/doc/poorwsgi',
         ['doc/ChangeLog', 'doc/licence.txt', 'README.rst',
          'CONTRIBUTION.rst'])
         ] + find_data_files("examples", "share/poorwsgi/examples"),
    license="BSD",
    license_files='doc/licence.txt',
    long_description=doc(),
    long_description_content_type="text/x-rst",
    keywords='web wsgi development',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Natural Language :: Czech",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    python_requires=">=3.8",
    cmdclass={'build_doc': BuildDoc,
              'clean_doc': CleanDoc,
              'install_doc': InstallDoc,
              'test': PyTest},
    tests_require=['pytest', 'requests', 'openapi-core', 'simplejson'],
    extras_require={
            'JSONGeneratorResponse': ['simplejson']}
)
