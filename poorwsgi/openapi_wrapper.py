"""OpenAPI core wrappers module.

This module, and only this module requires ``openapi_core`` python module from
https://github.com/p1c2u/openapi-core with version 0.13.0 or higher.

:Classes:   OpenAPIRequest, OpenAPIResponse
"""
import re

from openapi_core.validation.request.datatypes import (  # type: ignore
        RequestParameters)


class OpenAPIRequest():
    """Wrapper of PoorWSGI request to OpenAPIRequest.

    Be careful with testing of big incoming request body property, which
    returns Request.data depend on ``auto_data`` and ``data_size``
    configuration properties.
    """
    re_pattern = re.compile(r"<(\w*:)?(\w*)>")

    def __init__(self, request):
        self.request = request

    @property
    def host_url(self):
        """Return host_url for validator."""
        url = self.request.scheme + "://" + self.request.hostname
        if self.request.port != 80:
            url += ":%d" % self.request.port
        return url

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
        return RequestParameters(
            path=self.request.path_args,
            query=self.request.args,
            header=self.request.headers,
            cookie=self.request.cookies,
        )

    @property
    def body(self):
        """Return request data for validator."""
        return self.request.data

    @property
    def mimetype(self):
        """Return request mime_type for validator."""
        return self.request.mime_type


class OpenAPIResponse():
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
        """Return response status_code fro validator."""
        return self.response.status_code

    @property
    def mimetype(self):
        """Return response mime_type fro validator."""
        return self.response.content_type
