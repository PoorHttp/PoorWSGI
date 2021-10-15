"""Large file upload test."""

from wsgiref.simple_server import make_server
from sys import path as python_path
from time import sleep

import os
import logging as log

EXAMPLES_PATH = os.path.dirname(__file__)
python_path.insert(0, os.path.abspath(
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.request import FieldStorage  # noqa
from poorwsgi.response import HTTPException  # noqa

logger = log.getLogger()
logger.setLevel("DEBUG")
app = application = Application("large_file")
app.debug = True
app.auto_form = False


class Dummy():
    """Dummy File Object"""
    def __init__(self, filename, size):
        log.debug("Start uploading file: %s [%d]", filename, size)
        self.size = size
        self.uploaded = 0

    def write(self, data):
        """Only count uploaded data size."""
        self.uploaded += len(data)
        log.debug("Uploading ... %d", self.uploaded/self.size*100)
        sleep(0.0001)

    def seek(self, size):
        """Dummy seek"""
        if self.size == -1:
            return self.uploaded
        return size

    def close(self):
        """Print process stats."""
        if self.uploaded == self.size:
            log.info("Successfully saved")
        elif self.uploaded < self.size:
            log.error("file was not uploaded complete")
        else:
            log.error("Uploaded too much data ...")


def storage_factory(req):
    """Factory for craeting Dummy file instance"""
    file_length = req.content_length
    if file_length <= 0:
        raise HTTPException(400,
                            error="Missing content length or no content")

    def create(filename):
        """Create Dummy File object"""
        log.debug("file_callback....")
        return Dummy(filename, file_length)

    return create


@app.route('/', method=state.METHOD_GET_POST)
def root(req):
    """Return Root (Index) page."""
    if req.method == 'POST':
        FieldStorage(
            req, keep_blank_values=app.keep_blank_values,
            strict_parsing=app.strict_parsing,
            file_callback=storage_factory(req))

    return """
    <html>
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
        <form method="post" enctype="multipart/form-data">
          <input type="file" name="file"/>
          <input type="submit" value="Send"/>
        </form>

        <hr>
        <small>Copyright (c) 2021 Ondřej Tůma. See
          <a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>
        </small>
      </body>
    </html>"""


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
