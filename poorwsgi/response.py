"""
Poor WSGI Response classes.

:Exceptions:    HTTPException
:Classes:       Response, FileResponse, GeneratorResponse,
                StrGeneratorResponse, EmptyResponse, RedirectResponse
:Functions:     make_response, redirect, abort
"""

from http.client import responses
from io import BytesIO
from os import access, R_OK, fstat
from logging import getLogger

import mimetypes

from poorwsgi.state import HTTP_OK, \
    HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY
from poorwsgi.request import Headers

log = getLogger('poorwsgi')


class IBytesIO(BytesIO):
    """Class for returning bytes when is iterate."""

    def read_kilo(self):
        """Read 1024 bytes from buffer."""
        return self.read(1024)

    def __iter__(self):
        """Iterate object by 1024 bytes."""
        return iter(self.read_kilo, b'')


class HTTPException(Exception):
    """HTTP Exception to fast stop work."""
    def __init__(self, arg):
        """status_code is one of HTTP_* status code from state module.

        If response is set, that will use, otherwise the handler from
        Application will be call."""
        assert isinstance(arg, (int, Response))
        super(HTTPException, self).__init__(arg)


class Response:
    """HTTP Response object.

    This is base Response object which is process with PoorWSGI application.
    """
    def __init__(self, data=b'', content_type="text/html; charset=utf-8",
                 headers=None, status_code=HTTP_OK):
        assert isinstance(status_code, int)
        assert isinstance(data, (str, bytes))

        # String. The content type. Another way to set content_type is via
        # headers_out object property. Default is text/html; charset=utf-8
        self.content_type = content_type

        # A Headers object representing the headers to be sent to the client.
        if isinstance(headers, Headers):
            self.__headers = headers
        elif headers is None:
            self.__headers = Headers(
                (("X-Powered-By", "Poor WSGI for Python"),))
        else:
            self.__headers = Headers(headers)

        # Status. One of state.HTTP_* values.
        self.__status_code = status_code
        self.__reason = responses[self.__status_code]

        # The content length header was set automatically from buffer length.
        if isinstance(data, bytes):
            self.__buffer = IBytesIO(data)
            self.__content_length = len(data)
        else:
            data = data.encode("utf-8")
            self.__buffer = IBytesIO(data)
            self.__content_length = len(data)

    @property
    def status_code(self):
        """Http status code, which is **state.HTTP_OK (200)** by default.

        If you want to set this variable (which is very good idea in http_state
        handlers), it is good solution to use some of ``HTTP_`` constant from
        state module.
        """
        return self.__status_code

    @status_code.setter
    def status_code(self, value):
        if value not in responses:
            raise ValueError("Bad response status %s" % value)
        self.__status_code = value
        self.__reason = responses[self.__status_code]

    @property
    def reason(self):
        """HTTP response is set automatically with setting status_code.

        Setting response message is not good idea, but you can create
        own class based on Response, when you can override status_code setter.
        """
        return self.__reason

    @property
    def content_length(self):
        """Return content_length of response.

        That is size of internal buffer.
        """
        return self.__content_length

    @property
    def headers(self):
        """Reference to output headers object."""
        return self.__headers

    @headers.setter
    def headers(self, value):
        if isinstance(value, Headers):
            self.__headers = value
        else:
            self.__headers = Headers(value)

    @property
    def data(self):
        """Return data content."""
        self.__buffer.seek(0)
        return self.__buffer.read()

    def add_header(self, name, value, **kwargs):
        """Call Headers.add_header on headers object."""
        self.__headers.add_header(name, value, **kwargs)

    def write(self, data):
        """Write data to internal buffer."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.__content_length += len(data)
        self.__buffer.write(data)

    def __start_response__(self, start_response):
        if self.__status_code == 304:
            # Not Modified MUST NOT include other entity-headers
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
            if 'Content-Encoding' in self.__headers \
                    or 'Content-Language' in self.__headers \
                    or 'Content-Length' in self.__headers \
                    or 'Content-Location' in self.__headers \
                    or 'Content-MD5' in self.__headers \
                    or 'Content-Range' in self.__headers \
                    or 'Content-Type' in self.__headers:
                log.warning('Some entity header in Not Modified response')
            if 'Date' not in self.__headers:
                log.warning('Missing Date header in Not Modified response')
        else:
            if self.content_type \
                    and not self.__headers.get('Content-Type'):
                self.__headers.add('Content-Type', self.content_type)
            elif not self.content_type \
                    and not self.__headers.get('Content-Type'):
                log.info('Content-type not set!')

            if self.__content_length \
                    and not self.__headers.get('Content-Length'):
                self.__headers.add('Content-Length',
                                   str(self.__content_length))
        # endif

        start_response(
            "%d %s" % (self.__status_code, self.__reason),
            list(self.__headers.items()))

    def __end_of_response__(self):
        """Method **for internal use only!**.

        This method was called from Application object at the end of request
        for returning right value to wsgi server.
        """
        self.__buffer.seek(0)
        return self.__buffer

    def __call__(self, start_response):
        self.__start_response__(start_response)
        return self.__end_of_response__()
# endclass


class FileResponse(Response):
    """Instead of send_file methods."""
    def __init__(self, path, content_type=None, headers=None,
                 status_code=HTTP_OK):
        if not access(path, R_OK):
            raise IOError("Could not stat file for reading")
        if content_type is None:     # auto mime type select
            (content_type, encoding) = mimetypes.guess_type(path)
        if content_type is None:     # default mime type
            content_type = "application/octet-stream"
        super(FileResponse, self).__init__(content_type=content_type,
                                           headers=headers,
                                           status_code=status_code)
        self.__buffer = open(path, 'rb')
        self.__content_length = fstat(self.__buffer.fileno()).st_size


class GeneratorResponse(Response):
    """For response, which use generator as returned value."""
    def __init__(self, generator, content_type="text/html; charset=utf-8",
                 headers=None, status_code=HTTP_OK):
        super(GeneratorResponse, self).__init__(content_type=content_type,
                                                headers=headers,
                                                status_code=status_code)
        self.__generator = generator

    def write(self, data):
        raise RuntimeError("Generator Reason can't write data")

    def __end_of_response__(self):
        return self.__generator


class StrGeneratorResponse(GeneratorResponse):
    """Generator response where generator returns str."""
    def __end_of_response__(self):
        return (it.encode("utf-8") for it in self.__generator)


class EmptyResponse(GeneratorResponse):
    """For situation, where only state could be return."""
    def __init__(self, status_code=HTTP_OK):
        super(EmptyResponse, self).__init__((), status_code=status_code)

    def __start_response__(self, start_response):
        start_response(
            "%d %s" % (self.__status_code, self.__reason), tuple())


class RedirectResponse(Response):
    """Redirect the browser to another location.

    When permanent is true, MOVED_PERMANENTLY status code is sent to the
    client, otherwise it is MOVED_TEMPORARILY. A short text is sent to the
    browser informing that the document has moved (for those rare browsers that
    do not support redirection); this text can be overridden by supplying
    a text string.
    """
    def __init__(self, location, permanent=False, message=b'', headers=None):
        if permanent:
            status_code = HTTP_MOVED_PERMANENTLY
        else:
            status_code = HTTP_MOVED_TEMPORARILY
        super(RedirectResponse, self).__init__(message,
                                               content_type="text/plain",
                                               headers=headers,
                                               status_code=status_code)
        self.add_header("Location", location)


def make_response(data, content_type="text/html; character=utf-8",
                  headers=None, status_code=HTTP_OK):
    """Create response from simple values.

    Data could be string, bytes, or bytes returns iterable object like file.
    """
    if isinstance(data, (str, bytes)):      # "hello world"
        return Response(data, content_type, headers, status_code)
    try:
        iter(data)
    except TypeError:
        raise RuntimeError("Data must be str, bytes or bytes returns iterable "
                           "object")
    return GeneratorResponse(data, content_type, headers, status_code)


def redirect(location, permanent=False, message=b'', headers=None):
    """Raise HTTPException with RedirectResponse response."""
    raise HTTPException(
        RedirectResponse(location, permanent, message, headers))


def abort(arg):
    """Raise HTTPException with arg."""
    raise HTTPException(arg)
