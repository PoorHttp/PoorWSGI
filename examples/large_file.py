"""Large file upload test."""
# pylint: disable=duplicate-code

from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
from time import time
from tempfile import TemporaryFile
from hashlib import sha256

import os
import sys
import logging as log

EXAMPLES_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

# pylint: disable=import-error, disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.fieldstorage import FieldStorageParser  # noqa
from poorwsgi.response import HTTPException  # noqa
from poorwsgi.results import hbytes  # noqa

logger = log.getLogger()
logger.setLevel("DEBUG")
app = application = Application("large_file")
app.debug = True
app.auto_form = False


class Blackhole:
    """Dummy File Object"""

    def __init__(self, filename):
        log.debug("Start uploading file: %s", filename)
        self.uploaded = 0
        self.__hash = sha256()

    def write(self, data):
        """Only count uploaded data size."""
        size = len(data)
        self.uploaded += size
        self.__hash.update(data)
        return size

    def seek(self, size):
        """Dummy seek"""
        if size == -1:
            return self.uploaded
        return size

    def hexdigest(self):
        """Return sha256 hexdigest of file."""
        return self.__hash.hexdigest()

    def close(self):
        """Dummy close"""


class Temporary:
    """Temporary file"""

    def __init__(self, filename):
        log.debug("Start uploading file: %s", filename)
        self.uploaded = 0
        self.__hash = sha256()
        # pylint: disable=consider-using-with
        self.__file = TemporaryFile('wb+')

    def write(self, data):
        """Only count uploaded data size."""
        size = self.__file.write(data)
        self.__hash.update(data)
        self.uploaded += size
        return size

    def seek(self, size):
        """Proxy to internal file object seek method."""
        return self.__file.seek(size)

    def read(self, size):
        """Proxy to internal file object read method."""
        return self.__file.seek(size)

    def close(self):
        """Proxy to internal file object close method."""
        return self.__file.close()

    def hexdigest(self):
        """Return sha256 hexdigest of file."""
        return self.__hash.hexdigest()


def blackhole_factory(req):
    """Factory for craeting Dummy file instance"""
    if req.content_length <= 0:
        raise HTTPException(400,
                            error="Missing content length or no content")

    def create(filename):
        """Create Blackhole File object"""
        log.debug(create.__doc__)
        return Blackhole(filename)

    return create


def temporary_factory(req):
    """Factory for craeting Dummy file instance"""
    if req.content_length <= 0:
        raise HTTPException(400,
                            error="Missing content length or no content")

    def create(filename):
        """Create Temporary File object"""
        log.debug(create.__doc__)
        return Temporary(filename)

    return create


def no_factory():
    """No factory callback"""


def original_factory():
    """Original factory callback"""


def html_form(req, file_callback):
    """Generate upload page for specified callback."""
    stats = ""
    hexdigest = ""
    if req.method == 'POST':
        start = time()
        bytes_read = 0
        hexdigest = ''
        # pylint: disable=comparison-with-callable
        if file_callback == no_factory:
            to_download = min(req.content_length, 65365)
            data = req.read(to_download)
            while data:
                bytes_read += len(data)
                to_download = min(req.content_length-bytes_read, 65365)
                data = req.read(to_download)
        elif file_callback == original_factory:
            parser = FieldStorageParser(
                    req.input, req.headers,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing)
            parser.parse()
        else:
            parser = FieldStorageParser(
                    req.input, req.headers,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing,
                    file_callback=file_callback(req))
            form = parser.parse()
            bytes_read = parser.bytes_read
            hexdigest = form['file'].file.hexdigest()

        end = time() - start
        size = hbytes(bytes_read)
        speed = hbytes(bytes_read / end)
        stats = (f"Upload: {size[0]:.2f}{size[1]} in {end}s -> "
                 f"{speed[0]:.2f}{speed[1]}ps SHA256: {hexdigest}")
        log.info(stats)

        if bytes_read != req.content_length:
            log.error("File uploading not complete")
            raise HTTPException(400, error="File uploading not complete")

    return """
    <html>
      <head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title>Upload form for %s</title>
        <style>
          body {width:90%%; max-width:900px; margin:auto; padding-top:30px;}
          h1 {text-align: center; color: #707070;}
        </style>
      </head>
      <body>
        <a href="/">/</a>
        <h1>Upload form for %s</h1>
        <form method="post" enctype="multipart/form-data">
          <input type="file" name="file"/>
          <input type="submit" value="Send"/>
        </form>
        <pre>%s</pre>
        <hr>
        <small>Copyright (c) 2021 Ondřej Tůma. See
          <a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>
        </small>
      </body>
    </html>""" % (file_callback.__name__, file_callback.__name__, stats)


@app.route('/blackhole', method=state.METHOD_GET_POST)
def blackhole_form(req):
    """Return form for blackhole callback."""
    return html_form(req, blackhole_factory)


@app.route('/temporary', method=state.METHOD_GET_POST)
def temporary_form(req):
    """Return form for temporary callback."""
    return html_form(req, temporary_factory)


@app.route('/no-factory', method=state.METHOD_GET_POST)
def no_form(req):
    """Return form for no Formfield."""
    return html_form(req, original_factory)


@app.route('/')
def root(req):
    """Return Root (Index) page."""
    assert req
    return """<html>
      <head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title>Large File Upload Example</title>
        <style>
          body {width:90%%; max-width:900px; margin:auto; padding-top:30px;}
          h1 {text-align: center; color: #707070;}
        </style>
      </head>
      <body>
        <h1>Large File Upload Example</h1>
        <ul>
          <li><a href="/blackhole">Blackhole file callback</a></li>
          <li><a href="/temporary">Temporary file callback</a></li>
          <li><a href="/no-factory">No Formfield</a></li>
        </ul>
        <hr>
        <small>Copyright (c) 2021 Ondřej Tůma. See
          <a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>
        </small>
      </body>
    </html>
    """


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """This class is identical to WSGIServer but uses threads to handle
    requests by using the ThreadingMixIn. This is useful to handle weg
    browsers pre-opening sockets, on which Server would wait indefinitely.
    """

    multithread = True
    daemon_threads = True


if __name__ == '__main__':
    ADDRESS = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    httpd = make_server(ADDRESS, 8080, app, ThreadingWSGIServer)
    print(f"Starting to serve on http://{ADDRESS}:8080")
    httpd.serve_forever()
