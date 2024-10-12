"""PoorWSGI reimplementation of legacy cgi.FieldStorage.

:Classes: FieldStorage, FieldStorageParser
:Functions: valid_boundary
"""

import re
import tempfile
import urllib.parse
import warnings
from abc import ABCMeta, abstractmethod
from email.parser import FeedParser
from io import BytesIO, StringIO, TextIOWrapper
from typing import Any, Callable, Optional, Union

from poorwsgi.headers import parse_header

_RE_STR_BOUNDARY = re.compile("^[ -~]{0,200}[!-~]$")
_RE_BIN_BOUNDARY = re.compile(b"^[ -~]{0,200}[!-~]$")


def valid_boundary(data):
    """Check valid boundary label.

    >>> valid_boundary("----WebKitFormBoundaryMPRpF8CUUmlmqKqy")
    True
    >>> valid_boundary(b"----WebKitFormBoundaryMPRpF8CUUmlmqKqy")
    True
    """
    if isinstance(data, bytes):
        return bool(_RE_BIN_BOUNDARY.match(data))
    return bool(_RE_STR_BOUNDARY.match(data))


class FieldStorageInterface(metaclass=ABCMeta):
    """FieldStorage Interface

    Implements methods getvalue, getfirst and getlist
    """

    @abstractmethod
    def __contains__(self, key: str) -> bool: ...

    @abstractmethod
    def __getitem__(self, key: str): ...

    def getvalue(self, key: str, default: Any = None,
                 func: Callable = lambda x: x):
        """Get but func is called for all values.

        Arguments:
            key : str
                key name
            default : None
                default value if key not found
            func : converter (lambda x: x)
                Function or class which processed value. Default type of value
                is bytes for files and string for others.
        """
        if key in self:
            return func(self[key])
        return default

    def getfirst(self, key: str, default: Any = None,
                 func: Callable = lambda x: x,
                 fce: Optional[Callable] = None):
        """Get first item from list for key or default.

        default : any
            Default value if key not exists.
        func : converter
            Function which processed value.
        fce : deprecated converter name
            Use func converter just like getvalue.
        """
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
            func = fce
        if key in self:
            value = self[key]
            if isinstance(value, list):
                return func(value[0])
            return func(value)
        return default

    def getlist(self, key: str, default: Optional[list] = None,
                func: Callable = lambda x: x,
                fce: Optional[Callable] = None):
        """Returns list of variable values for key or empty list.

        default : list or None
            Default list if key not exists.
        func : converter
            Function which processed each value.
        fce : deprecated converter name
            Use func converter just like getvalue.
        """
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
            func = fce
        if key in self:
            value = self[key]
            if isinstance(value, list):
                return [func(x) for x in value]
            return [func(value)]
        return default or []


class FieldStorage(FieldStorageInterface):
    """Class inspired by cgi.FieldStorage.

    Instead of FieldStorage from cgi module, this is only storage for fields,
    with some additional functionality in getfirst, getlist, getvalue or simple
    get method. They return values instead of __getitem__ ([]), which returns
    another FieldStorage.

    Available attributes:

    :name:          variable name, the same name from input attribute.
    :value:         property which returns content of field
    :type:          mime-type of variable. All variables have internal
                    mime-type, if that is no file, mime-type is text/plain.
    :type_options:  other content-type parameters, just like encoding.
    :disposition:   content disposition header if is set
    :disposition_options: other content-disposition parameters if are set.
    :filename:      if variable is file, filename is its name from form.
    :length:        field length if was set in header, -1 by default.
    :file:          file type instance, from you can read variable. This
                    instance could be TemporaryFile as default for files,
                    StringIO for normal variables or instance of your own file
                    type class, create from file_callback.
    :lists:         if variable is list of variables, this contains instances
                    of other fields.

    FieldStorage is create by FieldStorageParser.

    FieldStorage has context methods, so you cat read files like this:
    >>> field = FieldStorage("key")
    >>> field.file = StringIO("value")
    >>> with field:
    ...     print(field.value)
    value
    """

    name: Optional[str] = None
    filename: Optional[str] = None
    length: int
    file = None
    type: str
    type_options: dict
    disposition: str
    disposition_options: dict

    def __init__(self, name: Optional[str] = None,
                 value: Optional[str] = None):
        self.list: list[FieldStorage] = []
        self.name = name
        self._value = value

    def __del__(self):
        if self.file:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.close()

    def __repr__(self):
        """Return printable representation."""
        return f"FieldStorage({self.name}, {self.value or self.file})"

    def __bool__(self):
        """
        >>> field = FieldStorage("key", "value")
        >>> bool(field)
        True
        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key")]
        >>> bool(field)
        True
        >>> field = FieldStorage("key")
        >>> bool(field)
        False
        """
        return bool(self.list or self.value)

    def __iter__(self):
        """
        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "value")]
        >>> for key in field:
        ...     print(key, ":", field.get(key))
        key : value
        """
        return iter(self.keys())

    def __len__(self):
        """
        >>> field = FieldStorage()
        >>> len(field)  # no fields in field storage
        0
        >>> field.list = [FieldStorage("k1", "value"), FieldStorage("k2", "K")]
        >>> len(field)  # two different keys
        2
        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("k", "value"), FieldStorage("k", "K")]
        >>> len(field)  # one key with two values
        1
        """
        return len(self.keys())

    def __contains__(self, key: str):
        """
        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "value")]
        >>> "key" in field
        True
        >>> "no-key" in field
        False
        """
        if not self.list:
            return False
        return any(item.name == key for item in self.list)

    def __getitem__(self, key: str):
        """Returns field if exist.
        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "value")]
        >>> field["key"].value
        'value'
        """
        if not self.list:
            raise KeyError(key)

        found = []
        for item in self.list:
            if item.name == key:
                found.append(item)
        if not found:
            raise KeyError(key)
        if len(found) == 1:
            return found[0]
        return found

    @property
    def value(self) -> Optional[Union[str, bytes, list]]:
        """Return content of field.

        * If field is file, return it's content.
        * If field is string value, return string.
        * If field is list of other fields (root FieldStorage), return that
          list.

        >>> field = FieldStorage()
        >>> print(field.value)
        None
        >>> field.list = [FieldStorage("key", "value")]
        >>> field.value
        [FieldStorage(key, value)]
        >>> field = FieldStorage("key", "value")
        >>> field.value
        'value'
        >>> field = FieldStorage("key")
        >>> field.file = StringIO("string")
        >>> field.value
        'string'
        >>> field = FieldStorage("key")
        >>> field.file = BytesIO(b"bytes")
        >>> field.value
        b'bytes'
        """
        if self._value:
            return self._value
        if isinstance(self.file, (StringIO, BytesIO)):
            return self.file.getvalue()
        if self.file:
            self.file.seek(0)
            value = self.file.read()
            self.file.seek(0)
        elif self.list:
            value = self.list
        else:
            value = None
        return value

    def keys(self):
        """Dictionary like keys() method.

        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "value")]
        >>> field.keys()
        dict_keys(['key'])
        """
        return dict.fromkeys(k.name for k in self.list).keys()

    def get(self, key: str, default: Any = None):
        """Compatibility methods with dict.

        Return value of list of values if exists.

        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "value")]
        >>> field.get("key")
        'value'
        >>> field.get("zero", "0")
        '0'
        """
        if key in self:
            value = self[key]
            if isinstance(value, list):
                return [it.value for it in value]
            return value.value
        return default

    def getvalue(self, key: str, default: Any = None,
                 func: Callable = lambda x: x):
        """Get but func is called for all values.

        Arguments:
            key : str
                key name
            default : None
                default value if key not found
            func : converter (lambda x: x)
                Function or class which processed value. Default type of value
                is bytes for files and string for others.

        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "42")]
        >>> field.getvalue("key", func=int)
        42
        """
        if key in self:
            value = self[key]
            if isinstance(value, list):
                return [func(it.value) for it in value]
            return func(value.value)
        return default

    def getfirst(self, key: str, default: Any = None,
                 func: Callable = lambda x: x,
                 fce: Optional[Callable] = None):
        """Get first item from list for key or default.

        Use func converter just like getvalue.
        :fce: deprecated converter name.

        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "1"), FieldStorage("key", "2")]
        >>> field.getfirst("key", func=int)
        1
        """
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
            func = fce
        if key in self:
            value = self[key]
            if isinstance(value, list):
                return func(value[0].value)
            return func(value.value)
        return default

    def getlist(self, key: str, default: Optional[list] = None,
                func: Callable = lambda x: x,
                fce: Optional[Callable] = None):
        """Returns list of variable values for key or empty list.

        Use func converter just like getvalue.
        :fce: deprecated converter name

        >>> field = FieldStorage()
        >>> field.list = [FieldStorage("key", "1"), FieldStorage("key", "2")]
        >>> field.getlist("key", func=int)
        [1, 2]
        >>> field.getlist("no-key")
        []
        >>> field.getlist("no-key", default=["empty"])
        ['empty']
        """
        if fce:
            warnings.warn("Using deprecated fce argument. Use func instead.",
                          category=DeprecationWarning, stacklevel=1)
            func = fce
        value = self.getvalue(key, func=func)
        if isinstance(value, list):
            return value
        if value is None:
            return default or []
        return [value]


class FieldStorageParser:
    """Class inspired by cgi.FieldStorage.

    This is only parsing part of old FieldStorage. It contain methods for
    parsing POST form encoede in multipart/form-data or
    application/x-www-form-urlencoded which is default.

    It generate FieldStorage or Field in depennd on encoding. But it do it
    only from request body. FieldStorage has internal StringIO for all
    values which are not stored in file. Some small binary files can be stored
    in BytesIO. Limit for storing fields in temporary files is 8192 bytes.

    .. code:: python

        parser = FieldStorageParser(request.input, request.headers)
        form = parser.parse()
        assert isinstance(form, FieldStorage)

    """
    BUFSIZE = 8*1024  # buffering size for copy to file and storing StringIO

    def __init__(self, input_=None, headers=None, outerboundary=b'',
                 keep_blank_values=0, strict_parsing=0,
                 limit=None, encoding='utf-8', errors='replace',
                 max_num_fields=None, separator='&', file_callback=None):
        """Constructor.  Read multipart/* until last part.

        Arguments, all optional:

        :input\\_:    Request.input file object

        :headers:   header dictionary-like object

        :outerboundary: terminating multipart boundary
            (for internal use only)

        :keep_blank_values: flag indicating whether blank values in
            percent-encoded forms should be treated as blank strings.
            A true value indicates that blanks should be retained as
            blank strings.  The default false value indicates that
            blank values are to be ignored and treated as if they were
            not included.

        :strict_parsing:    flag indicating what to do with parsing errors.
            If false (the default), errors are silently ignored.
            If true, errors raise a ValueError exception.

        :limit: used internally to read parts of multipart/form-data forms,
            to exit from the reading loop when reached. It is the difference
            between the form content-length and the number of bytes already
            read

        :encoding, errors:  the encoding and error handler used to decode the
            binary stream to strings. Must be the same as the charset defined
            for the page sending the form (content-type : meta http-equiv or
            header)

        :max_num_fields:    int. If set, then parse throws a ValueError
            if there are more than n fields read by parse_qsl().

        :file_callback: function returns file class for own handling creating
            files for write operations. By this, you can write file from
            request direct to destionation without temporary files.
        """
        self.headers = headers
        self.outerboundary = outerboundary
        self.keep_blank_values = keep_blank_values
        self.strict_parsing = strict_parsing
        self.limit = limit
        self.encoding = encoding
        self.errors = errors
        self.max_num_fields = max_num_fields
        self.separator = separator
        self.file_callback = file_callback

        self.bytes_read = 0
        self.done = 0
        self.filename = None
        self.innerboundary = b""
        self.length = -1

        # self.input.read() must return bytes
        if isinstance(input_, TextIOWrapper):
            self.input = input_.buffer
        else:
            self.input = input_

    def _parse_content_type(self):
        """ Process content-type header

        Honor any existing content-type header.  But if there is no
        content-type header, use some sensible defaults.  Assume
        outerboundary is "" at the outer level, but something non-false
        inside a multi-part.  The default for an inner part is text/plain,
        but for an outer part it should be urlencoded.  This should catch
        bogus clients which erroneously forget to include a content-type
        header.

        See below for what we do if there does exist a content-type header,
        but it happens to be something we don't understand.
        """
        if 'content-type' in self.headers:
            ctype, pdict = parse_header(self.headers['content-type'])
        elif self.outerboundary:
            ctype, pdict = "text/plain", {}
        else:
            ctype, pdict = 'application/x-www-form-urlencoded', {}
        return ctype, pdict

    def parse(self) -> FieldStorage:
        """Read input and generate FieldStorage from that."""

        field = FieldStorage()

        # Process content-disposition header
        cdisp, pdict = "", {}
        if 'content-disposition' in self.headers:
            cdisp, pdict = parse_header(self.headers['content-disposition'])

        field.disposition = cdisp
        field.disposition_options = pdict

        field.name = pdict.get('name')
        field.filename = self.filename = pdict.get('filename')

        ctype, pdict = self._parse_content_type()
        field.type = ctype
        field.type_options = pdict

        if 'boundary' in pdict:
            self.innerboundary = pdict['boundary'].encode(self.encoding,
                                                          self.errors)

        clen = -1
        if 'content-length' in self.headers:
            try:
                clen = int(self.headers['content-length'])
            except ValueError:
                pass
        field.length = self.length = clen
        if self.limit is None and clen >= 0:
            self.limit = clen

        if ctype == 'application/x-www-form-urlencoded':
            field.list = self.read_urlencoded()
        elif ctype[:10] == 'multipart/':
            field.list = self.read_multi()
        else:
            field.file = self.read_single()
        return field

    def read_urlencoded(self):
        """Internal: read data in query string format."""
        qs = self.input.read(self.length)
        if not isinstance(qs, bytes):
            msg = f"{self.input} should return bytes, got {type(qs).__name__}"
            raise ValueError(msg)

        qs = qs.decode(self.encoding, self.errors)
        query = urllib.parse.parse_qsl(
            qs, self.keep_blank_values, self.strict_parsing,
            encoding=self.encoding, errors=self.errors,
            max_num_fields=self.max_num_fields, separator=self.separator)
        self.skip_lines()
        return [FieldStorage(key, value) for key, value in query]

    def _skip_to_boundary(self):
        """Check and read file until we've hit our inner boundary."""
        if not valid_boundary(self.innerboundary):
            msg = ('Invalid boundary in multipart form:'
                   f'{repr(self.innerboundary)}')
            raise ValueError(msg)

        first_line = self.input.readline()  # bytes
        if not isinstance(first_line, bytes):
            msg = (f"{self.input} should return bytes, "
                   f"got {type(first_line).__name__}")
            raise ValueError(msg)
        self.bytes_read += len(first_line)

        # Ensure that we consume the file until we've hit our inner boundary
        while (first_line.strip() != (b"--" + self.innerboundary) and
                first_line):
            first_line = self.input.readline()
            self.bytes_read += len(first_line)

    def read_multi(self):
        """Internal: read a part that is itself multipart."""
        self._skip_to_boundary()
        max_num_fields = self.max_num_fields
        _list = []

        while True:
            parser = FeedParser()
            hdr_text = b""
            while True:
                data = self.input.readline()
                hdr_text += data
                if not data.strip():
                    break
            if not hdr_text:
                break
            # parser takes strings, not bytes
            self.bytes_read += len(hdr_text)
            parser.feed(hdr_text.decode(self.encoding, self.errors))
            headers = parser.close()

            # Some clients add Content-Length for part headers, ignore them
            if 'content-length' in headers:
                del headers['content-length']

            limit = None if self.limit is None \
                else self.limit - self.bytes_read
            field_parser = self.__class__(self.input, headers,
                                          self.innerboundary,
                                          self.keep_blank_values,
                                          self.strict_parsing, limit,
                                          self.encoding, self.errors,
                                          max_num_fields,
                                          self.separator,
                                          self.file_callback)
            part = field_parser.parse()

            if max_num_fields is not None:
                max_num_fields -= 1
                if part.list:
                    max_num_fields -= len(part.list)
                if max_num_fields < 0:
                    raise ValueError('Max number of fields exceeded')

            self.bytes_read += field_parser.bytes_read

            _list.append(part)
            if field_parser.done or self.bytes_read >= self.length > 0:
                break
        self.skip_lines()
        return _list

    def read_single(self):
        """Internal: read an atomic part."""
        if self.length >= 0:
            file = self.read_binary()
            self.skip_lines()
        else:
            file = self.read_lines()
        file.seek(0)
        return file

    def read_binary(self):
        """Internal: read binary data."""
        file = self.make_file()
        todo = self.length
        if todo >= 0:
            while todo > 0:
                data = self.input.read(min(todo, self.BUFSIZE))
                if not isinstance(data, bytes):
                    msg = (f"{self.input} should return bytes, "
                           f"got {type(data).__name__}")
                    raise ValueError(msg)
                self.bytes_read += len(data)
                if not data:
                    self.done = -1
                    break
                file.write(data)
                todo = todo - len(data)
        return file

    def read_lines(self):
        """Internal: read lines until EOF or outerboundary."""
        if self.filename and self.file_callback:
            file = self.make_file()
        elif self.filename:
            file = BytesIO()  # store data as bytes for files
        else:
            file = StringIO()  # as strings for other fields

        if self.outerboundary:
            file = self.read_lines_to_outerboundary(file)
        else:
            file = self.read_lines_to_eof(file)
        return file

    def _write(self, line, file):
        """line is always bytes, not string"""
        if isinstance(file, (BytesIO, StringIO)):  # if file is in memory
            if file.tell() + len(line) > self.BUFSIZE:
                _file = self.make_file()
                _file.write(file.getvalue())
                file = _file
        if self.filename:
            file.write(line)  # binary file (bytes)
        else:
            # decode to string
            file.write(line.decode(self.encoding, self.errors))
        return file

    def read_lines_to_eof(self, file):
        """Internal: read lines until EOF."""
        while 1:
            line = self.input.readline(1 << 16)
            self.bytes_read += len(line)
            if not line:
                self.done = -1
                break
            file = self._write(line, file)
        return file

    def read_lines_to_outerboundary(self, file):  # noqa: C901
        """Internal: read lines until outerboundary.
        Data is read as bytes: boundaries and line ends must be converted
        to bytes for comparisons.
        """
        next_boundary = b"--" + self.outerboundary
        last_boundary = next_boundary + b"--"
        delim = b""
        last_line_lfend = True
        _read = 0
        while 1:

            if self.limit is not None and 0 <= self.limit <= _read:
                break
            line = self.input.readline(1 << 16)
            self.bytes_read += len(line)
            _read += len(line)
            if not line:
                self.done = -1
                break
            if delim == b"\r":
                line = delim + line
                delim = b""
            if line.startswith(b"--") and last_line_lfend:
                strippedline = line.rstrip()
                if strippedline == next_boundary:
                    break
                if strippedline == last_boundary:
                    self.done = 1
                    break
            odelim = delim
            if line.endswith(b"\r\n"):
                delim = b"\r\n"
                line = line[:-2]
                last_line_lfend = True
            elif line.endswith(b"\n"):
                delim = b"\n"
                line = line[:-1]
                last_line_lfend = True
            elif line.endswith(b"\r"):
                # We may interrupt \r\n sequences if they span the 2**16
                # byte boundary
                delim = b"\r"
                line = line[:-1]
                last_line_lfend = False
            else:
                delim = b""
                last_line_lfend = False
            file = self._write(odelim + line, file)
        return file

    def skip_lines(self):
        """Internal: skip lines until outer boundary if defined."""
        if not self.outerboundary or self.done:
            return
        next_boundary = b"--" + self.outerboundary
        last_boundary = next_boundary + b"--"
        last_line_lfend = True
        while True:
            line = self.input.readline(1 << 16)
            self.bytes_read += len(line)
            if not line:
                self.done = -1
                break
            if line.endswith(b"--") and last_line_lfend:
                strippedline = line.strip()
                if strippedline == next_boundary:
                    break
                if strippedline == last_boundary:
                    self.done = 1
                    break
            last_line_lfend = line.endswith(b'\n')

    def make_file(self):
        """Return readable and writable temporery file.

        If filename and file_callback was set, file_callback is called instead
        of creating temporary file.

        """
        if self.filename and self.file_callback:
            return self.file_callback(self.filename)
        if self.filename:
            return tempfile.TemporaryFile("wb+")
        return tempfile.TemporaryFile("w+",
                                      encoding=self.encoding, newline='\n')
