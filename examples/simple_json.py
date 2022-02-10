"""This is example and test JSON application for PoorWSGI connector.

This sample testing example is free to use, modify and study under same BSD
licence as PoorWSGI. So enjoy it ;)
"""

from wsgiref.simple_server import make_server
from sys import path as python_path
from json import dumps

import os

EXAMPLES_PATH = os.path.dirname(__file__)
python_path.insert(0, os.path.abspath(
    os.path.join(EXAMPLES_PATH, os.path.pardir)))

# pylint: disable=import-error, wrong-import-position
from poorwsgi import Application, state  # noqa
from poorwsgi.response import JSONResponse, JSONGeneratorResponse # noqa
from poorwsgi.request import parse_json_request # noqa

try:
    import uwsgi  # type: ignore

except ModuleNotFoundError:
    uwsgi = None  # pylint: disable=invalid-name

app = application = Application("JSON")
app.debug = True


@app.route('/test/json', method=state.METHOD_GET_POST)
def test_json(req):
    """Test GET / POST json"""
    # numbers are complete list
    data = req.json
    if req.is_chunked_request:
        raw = b''
        # chunk must be read with extra method, uwsgi has own
        chunk = uwsgi.chunked_read() if uwsgi else req.read_chunk()
        while chunk:
            raw += chunk
            chunk = uwsgi.chunked_read() if uwsgi else req.read_chunk()
        data = parse_json_request(raw, req.charset)

    return JSONResponse(status_code=418, message="I'm teapot :-)",
                        numbers=list(range(5)),
                        request=data)


@app.route('/test/json-generator', method=state.METHOD_GET)
def test_json_generator(req):
    """Test JSON Generator"""
    # numbers are generator, which are iterate on output
    return JSONGeneratorResponse(status_code=418, message="I'm teapot :-)",
                                 numbers=range(5),
                                 request=req.json)


@app.route('/timestamp')
def get_timestamp(req):
    """Return simple json with req.start_time timestamp"""
    return JSONResponse(timestamp=req.start_time)


@app.route('/test/headers')
def test_headers(req):
    """Request headers response."""
    return dumps(
        {"Content-Type": (req.mime_type, req.charset),
         "Content-Length": req.content_length,
         "Host": req.hostname,
         "Accept": req.accept,
         "Accept-Charset": req.accept_charset,
         "Accept-Encoding": req.accept_encoding,
         "Accept-Language": req.accept_language,
         "Accept-MimeType": {
            "html": req.accept_html,
            "xhtml": req.accept_xhtml,
            "json": req.accept_json
         },
         "XMLHttpRequest": req.is_xhr}
    ), "application/json"


if __name__ == '__main__':
    httpd = make_server('127.0.0.1', 8080, app)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
