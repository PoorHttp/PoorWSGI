"""Classes that are used for managing headers.

:Classes:   Headers
:Functions: parse_negotiation, render_negotiation
"""
from collections.abc import Mapping
from logging import getLogger
from wsgiref.headers import _formatparam  # type: ignore

import re

from datetime import datetime, timezone
from typing import Union, List, Tuple, Optional, Dict

log = getLogger('poorwsgi')
# pylint: disable=consider-using-f-string

# https://httpwg.org/specs/rfc9110.html#field.date
# e.g. Tue, 15 Nov 1994 08:12:31 GMT
HEADER_DATETIME_FORMAT = "%a, %d %b %Y %X GMT"
RE_BYTES_RANGE = re.compile(r"(\d*)-(\d*),?")

HeadersList = Union[List, Tuple, set, dict]
RangeList = List[Tuple[Optional[int], Optional[int]]]


def _parseparam(s):
    """Parse a parameter list, handling quoted strings."""
    while s[:1] == ';':
        s = s[1:]
        end = s.find(';')
        while end > 0 and (s.count('"', 0, end) - s.count('\\"', 0, end)) % 2:
            end = s.find(';', end + 1)
        if end < 0:
            end = len(s)
        f = s[:end]
        yield f.strip()
        s = s[end:]


def parse_header(line):
    """Parses a Content-Type-like header.

    Returns the main content type and a dictionary of options.

    >>> parse_header("text/html; charset=latin-1")
    ('text/html', {'charset': 'latin-1'})
    >>> parse_header("text/plain")
    ('text/plain', {})
    """
    parts = _parseparam(';' + line)
    key = parts.__next__()
    pdict = {}
    for p in parts:
        i = p.find('=')
        if i >= 0:
            name = p[:i].strip().lower()
            value = p[i+1:].strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
                value = value.replace('\\\\', '\\').replace('\\"', '"')
            pdict[name] = value
    return key, pdict


def parse_negotiation(value: str):
    """Parses content negotiation headers into a list of (value, quality)
    tuples.

    >>> parse_negotiation('gzip;q=1.0, identity;q=0.5, *;q=0')
    [('gzip', 1.0), ('identity', 0.5), ('*', 0.0)]
    >>> parse_negotiation('text/html;level=1, text/html;level=2;q=0.5')
    [('text/html;level=1', 1.0), ('text/html;level=2', 0.5)]
    """
    values = []
    for item in value.split(','):
        pair = item.split(';q=')
        if pair[0] == item:
            values.append((item.strip(), 1.0))
            continue
        try:
            quality = float(pair[1])
        except (IndexError, ValueError):
            quality = 1.0
        values.append((pair[0].strip(), quality))
    return values


def render_negotiation(negotation: List[Tuple]):
    """Renders a negotiation header value from tuples.

    >>> render_negotiation([('gzip',1.0), ('*',0)])
    'gzip;q=1.0, *;q=0'
    >>> render_negotiation((('gzip',1.0), ('compress',)))
    'gzip;q=1.0, compress'
    >>> render_negotiation((('text/html;level=1',),
    ...                     ('text/html;level=2', 0.5)))
    'text/html;level=1, text/html;level=2;q=0.5'
    """
    values = []
    for nego in negotation:
        values.append(';q='.join(map(str, nego)))
    return ', '.join(values)


def parse_range(value: str) -> Dict[str, RangeList]:
    """Parses an HTTP Range header.

    Parses the `Range` header value and returns a dictionary with the units
    key and a list of range tuples.

    see: https://www.rfc-editor.org/rfc/rfc9110.html#name-range-requests

    >>> parse_range("bytes=0-499")
    {'bytes': [(0, 499)]}
    >>> parse_range("units=500-999")
    {'units': [(500, 999)]}
    >>> parse_range("bytes=-500")
    {'bytes': [(None, 500)]}
    >>> parse_range("bytes=9500-")
    {'bytes': [(9500, None)]}
    >>> parse_range("chunks=500-600,601-999")
    {'chunks': [(500, 600), (601, 999)]}
    >>> parse_range("bytes=0-1,1-2,1-,-5")
    {'bytes': [(0, 1), (1, 2), (1, None), (None, 5)]}
    >>> parse_range("bytes=0-499")
    {'bytes': [(0, 499)]}
    >>> parse_range("invalid")
    {}
    >>> parse_range("invalid=a-b")
    {'invalid': []}
    """
    try:
        unit, pairs = value.split("=")
        ranges: RangeList = []
        for start, end in RE_BYTES_RANGE.findall(pairs):
            if not start and not end:
                log.warning("Invalid range value, probably not number")
                continue
            ranges.append((
                    int(start) if start else None,
                    int(end) if end else None))
        return {unit: ranges}
    except ValueError:
        log.error("Invalid Range header value `%s`", value)
        return {}


def datetime_to_http(value: datetime):
    """Returns an HTTP Date from a timestamp.

    >>> datetime_to_http(datetime.fromtimestamp(0, timezone.utc))
    'Thu, 01 Jan 1970 00:00:00 GMT'
    """
    return value.strftime(HEADER_DATETIME_FORMAT)


def time_to_http(value: Optional[Union[int, float]] = None):
    """Returns an HTTP Date from a timestamp.

    >>> time_to_http(0)
    'Thu, 01 Jan 1970 00:00:00 GMT'
    >>> time_to_http()  # doctest: +ELLIPSIS
    '... GMT'
    """
    if value is not None:
        return datetime_to_http(datetime.fromtimestamp(int(value),
                                timezone.utc))
    return datetime_to_http(datetime.now(timezone.utc))


def http_to_datetime(value: str):
    """Returns a datetime from an HTTP Date string.

    >>> http_to_datetime("Thu, 01 Jan 1970 00:00:00 GMT")
    datetime.datetime(1970, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    """
    return datetime.strptime(
            value,
            HEADER_DATETIME_FORMAT).replace(tzinfo=timezone.utc)


def http_to_time(value: str):
    """Returns a timestamp from an HTTP Date.

    >>> http_to_time("Thu, 01 Jan 1970 00:00:00 GMT")
    0
    """
    return int(http_to_datetime(value).timestamp())


class ContentRange:
    """The Content-Range header.

    >>> str(ContentRange(1, 2))
    'bytes 1-2/*'
    >>> str(ContentRange(1, 2, 10))
    'bytes 1-2/10'
    >>> str(ContentRange(2, 5, units="lines"))
    'lines 2-5/*'
    """
    # pylint: disable=too-few-public-methods
    start: int
    end: int
    units: str
    full: Union[int, str]

    def __init__(self, start=0, end=0, full="*", units="bytes"):
        self.start = start
        self.end = end
        self.full = full
        self.units = units

    def __str__(self):
        return f"{self.units} {self.start}-{self.end}/{self.full}"


class Headers(Mapping):
    """A class inherited from collections.Mapping.

    As PEP 0333, respectively RFC 2616, states, all header names must
    contain only US-ASCII characters, excluding control characters or
    separators. Header values must be stored in strings encoded in
    ISO-8859-1. The Headers.add and Headers.add_header methods of this
    class automatically convert values from UTF-8 to ISO-8859-1
    encoding if possible. Therefore, all modification methods must use
    UTF-8 strings.

    Some headers can be set twice. Currently, a response can contain
    multiple ``Set-Cookie`` headers, but you can use the add_header
    method to add multiple headers with the same name. Alternatively,
    you can create headers from tuples, which is used in Request.

    When multiple headers with the same name are set in an HTTP request,
    the server joins their values into one.

    An empty header is not allowed.

    >>> headers = Headers({'X-Powered-By': 'Test'})
    >>> headers['X-Powered-By']
    'Test'
    >>> headers['x-powered-by']
    'Test'
    >>> headers.get('X-Powered-By')
    'Test'
    >>> headers.get('x-powered-by')
    'Test'
    >>> 'X-Powered-By' in headers
    True
    >>> 'x-powered-by' in headers
    True
    """
    def __init__(self, headers: Optional[HeadersList] = None,
                 strict: bool = True):
        """Headers constructor.

        A Headers object can be created from a list, set, or tuple of
        (name, value) pairs, or from a dictionary. All names or values
        must be ISO-8859-1 encodable. If not, an AssertionError will be
        raised.

        If strict is False, header names and values are not encoded to
        ISO-8859-1. This is for input headers only.
        """
        headers = headers or []
        if isinstance(headers, (list, tuple, set)):
            if strict:
                self.__headers = list(
                    (Headers.iso88591(k), Headers.iso88591(v))
                    for k, v in headers)
            else:
                self.__headers = list((k, v) for k, v in headers)
        elif isinstance(headers, dict):
            if strict:
                self.__headers = list(
                    (Headers.iso88591(k), Headers.iso88591(v))
                    for k, v in headers.items())
            else:
                self.__headers = list((k, v) for k, v in headers.items())
        else:
            raise TypeError("headers must be tuple, list or set "
                            "of str pairs, or dict "
                            "(got {0})".format(type(headers)))

    def __len__(self):
        """Returns the number of header items."""
        return len(self.__headers)

    def __getitem__(self, name: str):
        """Returns the header item identified by its lowercase name."""
        name = Headers.iso88591(name.lower())
        for k, val in self.__headers:
            if k.lower() == name:
                return val
        raise KeyError("{0!r} is not registered".format(name))

    def __delitem__(self, name: str):
        """Deletes the item identified by its lowercase name."""
        name = Headers.iso88591(name.lower())
        self.__headers = list(kv for kv in self.__headers
                              if kv[0].lower() != name)

    def __setitem__(self, name: str, value: str):
        """Deletes an item if it exists and sets its new value."""
        del self[name]
        self.add_header(name, value)

    def __iter__(self):
        return iter(self.__headers)

    def __repr__(self):
        return "Headers(%r)" % repr(tuple(self.__headers))

    def names(self):
        """Returns a tuple of header names."""
        return tuple(k for k, v in self.__headers)

    def keys(self):
        """An alias for the names method."""
        return self.names()

    def values(self):
        """Returns a tuple of header values."""
        return tuple(v for k, v in self.__headers)

    def get_all(self, name: str):
        """Returns a tuple of all values for the header identified by its
        lowercase name.

        >>> headers = Headers([('Set-Cookie', 'one'), ('Set-Cookie', 'two')])
        >>> headers.get_all('Set-Cookie')
        ('one', 'two')
        >>> headers.get_all('X-Test')
        ()
        """
        name = Headers.iso88591(name.lower())
        return tuple(kv[1] for kv in self.__headers if kv[0].lower() == name)

    def items(self):
        """Returns a tuple of header (key, value) pairs."""
        return tuple(self.__headers)

    def setdefault(self, name: str, value: str):
        """Sets a header value if it does not exist, and returns its value."""
        res = self.get(name)
        if res is None:
            self.add_header(name, value)
            return value
        return res

    def add(self, name: str, value: str):
        """Sets a header name to a value.

        Duplicate names are not allowed, except for ``Set-Cookie``.
        """
        if name != "Set-Cookie" and name in self:
            raise KeyError("Key %s exist." % name)
        self.add_header(name, value)

    def add_header(self, name: str,
                   value: Optional[Union[str, List[Tuple]]] = None,
                   **kwargs):
        """Extended header setting.

        name
            The header field to add.

        value
            If the value is a list of tuples, render_negotiation will be used.

        kwargs
            Arguments can be used to set additional value parameters for the
            header field, with underscores converted to dashes. Normally, the
            parameter will be added as name="value".

        .. code:: python

            h.add_header('X-Header', 'value')
            h.add_header('Content-Disposition', 'attachment',
                         filename='image.png')
            h.add_header('Accept-Encoding', [('gzip',1.0), ('*',0)])

        All names must be US-ASCII strings, excluding control characters
        or separators.
        """
        parts = []

        if isinstance(value, (list, tuple)):
            parts.append(Headers.iso88591(render_negotiation(value)))

        else:
            if value is not None:
                parts.append(Headers.iso88591(value))

            for k, val in kwargs.items():
                k = Headers.iso88591(k)
                if val is None:
                    parts.append(k.replace('_', '-'))
                else:
                    parts.append(_formatparam(k.replace('_', '-'),
                                              Headers.iso88591(val)))
        if not parts:
            raise ValueError("Header value must be set.")
        self.__headers.append((Headers.iso88591(name), "; ".join(parts)))

    @staticmethod
    def iso88591(value: str) -> str:
        """Performs automatic conversion to ISO-8859-1 strings.

        Converts from UTF-8 to ISO-8859-1 strings. This means all input values
        for the Headers class must be UTF-8 strings.
        """
        try:
            if isinstance(value, str):
                return value.encode('utf-8').decode('iso-8859-1')

        except UnicodeError as err:
            raise ValueError("Header name/value must be iso-8859-1 "
                             "encoded (got {0})".format(value)) from err
        raise TypeError("Header name/value must be of type str "
                        "(got {0})".format(value))

    @staticmethod
    def utf8(value: str) -> str:
        """Performs automatic conversion to UTF-8 strings."""
        try:
            return value.encode('iso-8859-1').decode('utf-8')
        except UnicodeError:
            return value  # probably utf-8 yet
