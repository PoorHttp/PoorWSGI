"""OpenAPI core wrappers module.

This module, and only this module requires ``openapi_core`` python module from
https://github.com/p1c2u/openapi-core with version 0.13.0 or higher.

:Classes:   OpenAPIRequest, OpenAPIResponse
"""
from collections import OrderedDict

import re

from openapi_core.protocols import Request, Response
from openapi_core.validation.request.datatypes import RequestParameters


class OpenAPIRequest(Request):
    """Wrapper of PoorWSGI request to OpenAPIRequest.

    Be careful with testing of big incoming request body property, which
    returns Request.data depend on ``auto_data`` and ``data_size``
    configuration properties. Request.data is available only when request
    Content-Length is available.
    """
    re_pattern = re.compile(r"<(\w*:)?(\w*)>")

    def __init__(self, request):
        self.request = request

    @property
    def host_url(self):
        """Return host_url for validator."""
        return self.request.construct_url('')

    @property
    def path(self):
        """Return method path"""
        return self.request.path

    @property
    def method(self):
        """Return method in lower case for validator."""
        return self.request.method.lower()

    @property
    def full_url_pattern(self):
        """Return full_url_pattern for validator."""
        if self.request.uri_rule is None:
            return self.host_url+self.request.uri
        return self.host_url+OpenAPIRequest.re_pattern.sub(
            r"{\2}", self.request.uri_rule)

    @property
    def parameters(self):
        """Return RequestParameters object for validator."""
        path_args = OrderedDict()
        for (key, val) in self.request.path_args.items():
            # allowed openapi core types...
            if (not isinstance(val, (float, int, str, bool)) and
                    val is not None):
                val = str(val)
            path_args[key] = val

        return RequestParameters(
            path=path_args,
            query=self.request.args,
            header=self.request.headers,
            cookie=self.request.cookies or {},
        )

    @property
    def body(self):
        """Return request data for validator."""
        return self.request.data

    @property
    def mimetype(self):
        """Return request mime_type for validator."""
        return self.request.mime_type


class OpenAPIResponse(Response):
    """Wrapper of PoorWSGI request to OpenAPIResponse."""

    def __init__(self, response):
        self.response = response

    @property
    def data(self):
        """Return response data for validator.

        Warning! This will not work for generator responses"
        """
        return self.response.data

    @property
    def status_code(self):
        """Return response status_code for validator."""
        return self.response.status_code

    @property
    def mimetype(self):
        """Return response mime_type for validator."""
        return self.response.headers.get(
                'Content-Type', self.response.content_type).split(';')[0]

    @property
    def headers(self):
        """Return response headers for validator."""
        return self.response.headers
