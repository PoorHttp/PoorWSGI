"""Upload file via WebDAV PUT method."""

from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
from hashlib import sha256
from tempfile import TemporaryFile

import os
import sys
import logging as log

EXAMPLES_PATH = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

# pylint: disable=import-error, disable=wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.response import JSONResponse  # noqa

logger = log.getLogger()
logger.setLevel("DEBUG")
app = application = Application("large_file")
app.debug = True

# pylint: disable=duplicate-code


@app.route('/blackhole/<filename>', method=state.METHOD_PUT)
def blackhole_put(req, filename: str):
    """Upload file via PUT method like in webdav"""
    checksum = sha256()
    uploaded = 0

    if req.content_length > 0:
        block = min(app.cached_size, req.content_length)
        data = req.read(block)
        while data:
            uploaded += len(data)
            checksum.update(data)
            block = min(app.cached_size, req.content_length-uploaded)
            if block > 1:
                data = req.read(block)
            else:
                data = b''

    return JSONResponse(status_code=200, uploaded=uploaded,
                        checksum=checksum.hexdigest(), filename=filename)


@app.route('/temporary/<filename>', method=state.METHOD_PUT)
def temporary_put(req, filename: str):
    """Upload file via PUT method like in webdav"""
    checksum = sha256()
    uploaded = 0

    if req.content_length > 0:
        with TemporaryFile('wb+') as temp:
            block = min(app.cached_size, req.content_length)
            data = req.read(block)
            while data:
                uploaded += temp.write(data)
                checksum.update(data)
                block = min(app.cached_size, req.content_length-uploaded)
                if block > 1:
                    data = req.read(block)
                else:
                    data = b''

    return JSONResponse(status_code=200, uploaded=uploaded,
                        checksum=checksum.hexdigest(), filename=filename)


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
          <input type="file" name="file"/>
        <ul>
          <li><a href="#blackhole" id="blackhole"/>Blackhole</a>
          <li><a href="#temporary" id="temporary"/>Temporary</a>
        </ul>
        <hr>
        <small>Copyright (c) 2021 Ondřej Tůma. See
          <a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>
        </small>
        <script>
          function upload(path){
            let file = document.querySelector('input[type=file]').files[0];
            if (file === undefined) {
                alert("No file selected.");
                return;
            }

            let ajax = new XMLHttpRequest();
            ajax.open("PUT", path+file.name, true);
            ajax.onload = function (ev) {
              alert(ajax.response);
            };

            const reader = new FileReader();
            reader.onload = function(e) {
                const blob = new Blob([new Uint8Array(e.target.result)],
                                      {type: file.type });
                ajax.send(blob);
            };
            reader.readAsArrayBuffer(file);
          }

          let blackhole = document.getElementById('blackhole');
          blackhole.addEventListener('click', function(event){
            upload('/blackhole/');
          });

          let temporary = document.getElementById('temporary');
          temporary.addEventListener('click', function(event){
            upload('/temporary/');
          });
        </script>
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
