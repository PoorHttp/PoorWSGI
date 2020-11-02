"""
Poor WSGI Response classes.

:Exceptions:    HTTPException
:Classes:       Response, JSONResponse, FileResponse, GeneratorResponse,
                StrGeneratorResponse, EmptyResponse, RedirectResponse
:Functions:     make_response, redirect, abort
"""

from http.client import responses
from io import BytesIO
from os import access, R_OK, fstat
from logging import getLogger
from json import dumps
from inspect import stack

import mimetypes

try:
    from simplejson import JSONEncoder as GJSONEncoder
except ImportError:
    GJSONEncoder = False

from poorwsgi.state import HTTP_OK, \
    HTTP_MOVED_PERMANENTLY, HTTP_MOVED_TEMPORARILY, HTTP_I_AM_A_TEAPOT
from poorwsgi.request import Headers

log = getLogger('poorwsgi')
# not in http.client.responses
responses[HTTP_I_AM_A_TEAPOT] = "I'm a teapot"


class IBytesIO(BytesIO):
    """Class for returning bytes when is iterate."""

    def read_kilo(self):
        """Read 1024 bytes from buffer."""
        return self.read(1024)

    def __iter__(self):
        """Iterate object by 1024 bytes."""
        return iter(self.read_kilo, b'')


class HTTPException(Exception):
    """HTTP Exception to fast stop work.

    Simple error exception:

    >>> HTTPException(404)  # doctest: +ELLIPSIS
    HTTPException(404, {}...)

    Exception with response:

    >>> HTTPException(Response(data=b'Created', status_code=201))
    ...                     # doctest: +ELLIPSIS
    HTTPException(<poorwsgi.response.Response object at 0x...>...)

    Attributes:

    >>> HTTPException(401, stale=True)  # doctest: +ELLIPSIS
    HTTPException(401, {'stale': True}...)
    """
    def __init__(self, arg, **kwargs):
        """status_code is one of HTTP_* status code from state module.

        If response is set, that will use, otherwise the handler from
        Application will be call."""
        assert isinstance(arg, (int, Response))
        super().__init__(arg, kwargs)


class Response:
    """HTTP Response object.

    This is base Response object which is process with PoorWSGI application.
    """
    def __init__(self, data=b'', content_type="text/html; charset=utf-8",
                 headers=None, status_code=HTTP_OK):
        assert isinstance(data, (str, bytes)), \
            "data is not string or bytes but %s" % type(data)
        assert isinstance(content_type, str), \
            "content_type is not string but `%s`" % content_type
        assert isinstance(status_code, int), \
            "status_code is not number but `%s`" % status_code

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
            # pylint: disable=too-many-boolean-expressions
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


class JSONResponse(Response):
    """Simple application/json response.

    ** kwargs from constructor are serialized to json structure.
    """
    def __init__(self, charset="utf-8", headers=None, status_code=HTTP_OK,
                 **kwargs):
        mime_type = "application/json"
        if charset:
            mime_type += "; charset="+charset

        super().__init__(dumps(kwargs), mime_type, headers, status_code)


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
        super().__init__(content_type=content_type,
                         headers=headers,
                         status_code=status_code)
        self.__buffer = open(path, 'rb')
        self.__content_length = fstat(self.__buffer.fileno()).st_size

    def write(self, data):
        raise RuntimeError("File Response can't write data")

    # must be redefined, because self.__buffer is private attribute
    @property
    def data(self):
        """Return data content."""
        self.__buffer.seek(0)
        return self.__buffer.read()

    # must be redefined, because self.__buffer is private attribute
    def __end_of_response__(self):
        """Method **for internal use only!**.

        This method was called from Application object at the end of request
        for returning right value to wsgi server.
        """
        self.__buffer.seek(0)
        return self.__buffer


class GeneratorResponse(Response):
    """For response, which use generator as returned value."""
    def __init__(self, generator, content_type="text/html; charset=utf-8",
                 headers=None, status_code=HTTP_OK):
        super().__init__(content_type=content_type,
                         headers=headers,
                         status_code=status_code)
        self.__generator = generator

    def write(self, data):
        """Not possible to write data ro GeneratorResponse."""
        raise RuntimeError("Generator Response can't write data")

    def __end_of_response__(self):
        return self.__generator


class StrGeneratorResponse(GeneratorResponse):
    """Generator response where generator returns str."""
    def __init__(self, generator, content_type="text/html; charset=utf-8",
                 headers=None, status_code=HTTP_OK):
        super().__init__(generator, content_type=content_type, headers=headers,
                         status_code=status_code)
        self.__generator = generator

    def __end_of_response__(self):
        return (it.encode("utf-8") for it in self.__generator)


if GJSONEncoder:
    class JSONGeneratorResponse(StrGeneratorResponse):
        """JSON Response for data from generator.

        Data will be processed in generator way, so they need to be buffered.
        This class need simplejson module.

        ** kwargs from constructor are serialized to json structure.
        """
        def __init__(self, charset="utf-8", headers=None, status_code=HTTP_OK,
                     **kwargs):
            mime_type = "application/json"
            if charset:
                mime_type += "; charset="+charset
            generator = GJSONEncoder(
                iterable_as_array=True).iterencode(kwargs)
            super().__init__(generator, mime_type, headers, status_code)


else:
    class JSONGeneratorResponse(GeneratorResponse):
        """JSON Response for data from generator.

        Data will be processed in generator way, so they need to be buffered.
        This class need simplejson module.
        """
        # pylint: disable=super-init-not-called
        def __init__(self):
            raise NotImplementedError(
                "JSONGeneratorResponse need simplejson module")


class EmptyResponse(GeneratorResponse):
    """For situation, where only state could be return."""
    def __init__(self, status_code=HTTP_OK):
        super().__init__((), status_code=status_code)

    @property
    def headers(self):
        """EmptyResponse don't have headers"""
        return Headers()

    @headers.setter
    def headers(self, value):
        # pylint: disable=unused-argument,logging-format-interpolation
        stack_record = stack()[1]
        log.warning("EmptyResponse don't use headers.\n"
                    "  File {1}, line {2}, in {3} \n"
                    "{0}".format(stack_record[4][0], *stack_record[1:4]))

    def add_header(self, *args, **kwargs):
        """EmptyResponse don't have headers"""
        # pylint: disable=unused-argument,logging-format-interpolation
        stack_record = stack()[1]
        log.warning("EmptyResponse don't use headers.\n"
                    "  File {1}, line {2}, in {3} \n"
                    "{0}".format(stack_record[4][0], *stack_record[1:4]))

    def __start_response__(self, start_response):
        start_response(
            "%d %s" % (self.status_code, self.reason), [])


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
        super().__init__(message,
                         content_type="text/plain",
                         headers=headers,
                         status_code=status_code)
        self.add_header("Location", location)


class ResponseError(RuntimeError):
    """Exception for bad response values."""


def make_response(data, content_type="text/html; charset=utf-8",
                  headers=None, status_code=HTTP_OK):
    """Create response from simple values.

    Data could be string, bytes, or bytes returns iterable object like file.
    """
    try:
        if isinstance(data, (str, bytes)):      # "hello world"
            return Response(data, content_type, headers, status_code)

        iter(data)  # try iter data
        return GeneratorResponse(data, content_type, headers, status_code)
    except Exception:  # pylint: disable=broad-except
        log.exception("Error in processing values: %s, %s, %s, %s",
                      type(data), type(content_type), type(headers),
                      type(status_code))

    raise ResponseError(
        "Returned data must by: <bytes|str>, <str>, <Headers|None>, <int>")


def redirect(location, permanent=False, message=b'', headers=None):
    """Raise HTTPException with RedirectResponse response."""
    raise HTTPException(
        RedirectResponse(location, permanent, message, headers))


def abort(arg):
    """Raise HTTPException with arg.

    Raise simple error exception:

    >>> abort(404)
    Traceback (most recent call last):
    ...
    poorwsgi.response.HTTPException: (404, {})

    Raise exception with response:

    >>> abort(Response(data=b'Created', status_code=201))
    Traceback (most recent call last):
    ...
    poorwsgi.response.HTTPException:
    (<poorwsgi.response.Response object at 0x...>, {})
    """
    raise HTTPException(arg)
