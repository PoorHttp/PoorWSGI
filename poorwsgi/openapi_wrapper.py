"""OpenAPI core wrappers module.

This module (and only this module) requires the ``openapi_core`` Python
module from https://github.com/p1c2u/openapi-core, with version 0.13.0
or higher.

:Classes:   OpenAPIRequest, OpenAPIResponse
"""
from collections import OrderedDict

import re

from openapi_core.protocols import Request, Response
from openapi_core.validation.request.datatypes import RequestParameters


class OpenAPIRequest(Request):
    """Wrapper of a PoorWSGI request to OpenAPIRequest.

    Be careful when testing large incoming request body properties, which
    return Request.data depending on the ``auto_data`` and ``data_size``
    configuration properties. Request.data is available only when the request's
    Content-Length is available.
    """
    re_pattern = re.compile(r"<(\w*:)?(\w*)>")

    def __init__(self, request):
        self.request = request

    @property
    def host_url(self):
        """Returns the host_url for the validator."""
        return self.request.construct_url('')

    @property
    def path(self):
        """Returns the method path."""
        return self.request.path

    @property
    def method(self):
        """Returns the method in lowercase for the validator."""
        return self.request.method.lower()

    @property
    def full_url_pattern(self):
        """Returns the full_url_pattern for the validator."""
        if self.request.uri_rule is None:
            return self.host_url+self.request.uri
        return self.host_url+OpenAPIRequest.re_pattern.sub(
            r"{\2}", self.request.uri_rule)

    @property
    def parameters(self):
        """Returns the RequestParameters object for the validator."""
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
        """Returns the request data for the validator."""
        return self.request.data

    @property
    def mimetype(self):
        """Returns the request MIME type for the validator."""
        return self.request.mime_type


class OpenAPIResponse(Response):
    """Wrapper of a PoorWSGI response to OpenAPIResponse."""

    def __init__(self, response):
        self.response = response

    @property
    def data(self):
        """Returns the response data for the validator.

        Warning! This will not work for generator responses.
        """
        return self.response.data

    @property
    def status_code(self):
        """Returns the response status_code for the validator."""
        return self.response.status_code

    @property
    def mimetype(self):
        """Returns the response MIME type for the validator."""
        return self.response.headers.get(
                'Content-Type', self.response.content_type).split(';')[0]

    @property
    def headers(self):
        """Returns the response headers for the validator."""
        return self.response.headers
