"""PoorWSGI setup.py"""
import logging
from os import environ, makedirs, path, walk, listdir
from shutil import copyfile, rmtree
from subprocess import call
from typing import ClassVar

from setuptools import Command, setup  # type: ignore

from poorwsgi.state import __version__

environ.update({'PYTHONPATH': 'poorwsgi'})

# pylint: disable=missing-function-docstring


def find_data_files(directory, target_folder=""):
    """Find files in directory, and prepare tuple for setup."""
    retval = []
    for root, _, files in walk(directory):
        if target_folder:
            retval.append((target_folder,
                           list(root + '/' + f for f in files
                                if f[0] != '.' and f[-1] != '~')))
        else:
            retval.append((root,
                           list(root + '/' + f for f in files
                                if f[0] != '.' and f[-1] != '~')))
    return retval


class BuildDoc(Command):
    """Build html documentation."""
    description = "build html documentation, need jinja24doc >= 1.1.0"
    user_options: ClassVar[list[tuple]] = [
        ("build-base=", "b",
         "base build directory (default: 'build.build-base')"),
        ('html-temp=', 't', "temporary documentation directory"),
        ('public', 'p', "build as part of public poorhttp web")
    ]

    build_base: str | None
    html_temp: str | None
    public: bool = False

    def initialize_options(self):
        self.build_base = None
        self.html_temp = None

    def finalize_options(self):
        self.set_undefined_options('build', ('build_base', 'build_base'))
        if self.html_temp is None:
            self.html_temp = path.join(self.build_base, 'html')

    def page(self, in_name, out_name=None):
        """Generate page."""
        if out_name is None:
            out_name = in_name
        with open(f'{self.html_temp}/{out_name}.html', 'w',
                  encoding="utf-8") as stdout:
            call([
                'jinja24doc', '-v', '--var', f'public={self.public}',
                f'_{in_name}.html', 'doc'
            ],
                 stdout=stdout)

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
        copyfile('doc/style.css', self.html_temp + '/style.css')
        copyfile('doc/web.css', self.html_temp + '/web.css')
        copyfile('doc/small-logo.png', self.html_temp + '/small-logo.png')


class CleanDoc(Command):
    """Clean temporary files from build_doc command."""
    description = "clean up temporary files from 'build_doc' command"
    user_options: ClassVar[list[tuple]] = [
        ('build-base=', 'b',
         "base build directory (default: 'build-html.build-base')"),
        ('html-temp=', 't', "temporary documentation directory")
    ]

    build_base: str | None
    html_temp: str | None

    def initialize_options(self):
        self.build_base = None
        self.html_temp = None

    def finalize_options(self):
        self.set_undefined_options('build_doc', ('build_base', 'build_base'),
                                   ('html_temp', 'html_temp'))

    def run(self):
        if path.exists(self.html_temp):
            if self.dry_run:
                return
            rmtree(self.html_temp)
        else:
            logging.warning("'%s' does not exist -- can't clean it",
                            self.html_temp)


class InstallDoc(Command):
    """Install documentation files."""
    description = "install html documentation"
    user_options: ClassVar[list[tuple]] = [
        ('build-base=', 'b',
         "base build directory (default: 'build-html.build-base')"),
        ('html-temp=', 't', "temporary documentation directory"),
    ]

    build_base: str | None
    html_temp: str | None
    dest_dir: str | None
    data_files: list[tuple]

    def initialize_options(self):
        self.build_base = None
        self.html_temp = None

    def finalize_options(self):
        self.set_undefined_options('build_doc', ('build_base', 'build_base'),
                                   ('html_temp', 'html_temp'))
        if self.dest_dir is None:
            self.dest_dir = path.join(self.install_data, "share", "doc",
                                      "poorwsgi", "html")

    def run(self):
        self.mkpath(self.dest_dir)
        for page in listdir(self.html_temp):
            src = f"{self.html_temp}/{page}"
            (out, _) = self.copy_file(src, self.dest_dir)
            self.outfiles.append(out)

    def get_inputs(self):
        # pylint: disable=no-self-use
        return []

    def get_outputs(self):
        return self.outfiles


def doc():
    """Return README.rst content."""
    with open('README.rst', 'r', encoding="utf-8") as readme:
        return readme.read().strip()


setup(name="PoorWSGI",
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
          'Tracker': 'https://github.com/PoorHttp/PoorWSGI/issues'
      },
      packages=['poorwsgi'],
      package_data={'': ['py.typed']},
      data_files=[('share/doc/poorwsgi', [
          'doc/ChangeLog', 'doc/licence.txt', 'README.rst', 'CONTRIBUTION.rst'
      ])] + find_data_files("examples", "share/poorwsgi/examples"),
      license="BSD",
      license_files='doc/licence.txt',
      long_description=doc(),
      long_description_content_type="text/x-rst",
      keywords='web wsgi development',
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Environment :: Web Environment", "Intended Audience :: Developers",
          "License :: OSI Approved :: BSD License",
          "Natural Language :: English", "Natural Language :: Czech",
          "Operating System :: MacOS :: MacOS X", "Operating System :: POSIX",
          "Operating System :: POSIX :: BSD",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python :: 3 :: Only",
          "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware",
          "Topic :: Software Development :: Libraries :: Python Modules"
      ],
      python_requires=">=3.8",
      cmdclass={
          'build_doc': BuildDoc,
          'clean_doc': CleanDoc,
          'install_doc': InstallDoc,
      },
      tests_require=['pytest', 'requests', 'openapi-core', 'simplejson'],
      extras_require={'JSONGeneratorResponse': ['simplejson']})
