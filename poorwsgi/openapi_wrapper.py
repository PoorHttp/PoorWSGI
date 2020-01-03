"""OpenAPI core wrappers module.

This module, and only this module requires ``openapi_core`` python module from
https://github.com/p1c2u/openapi-core.

:Classes:   OpenAPIRequest, OpenAPIResponse
"""
import re

from openapi_core.wrappers.base import BaseOpenAPIRequest, BaseOpenAPIResponse


class OpenAPIRequest(BaseOpenAPIRequest):
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
        return self.request.hostname

    @property
    def path(self):
        return self.request.uri

    @property
    def method(self):
        return self.request.method.lower()

    @property
    def path_pattern(self):
        if self.request.uri_rule is None:
            return self.request.uri
        return OpenAPIRequest.re_pattern.sub(
            r"{\2}", self.request.uri_rule)

    @property
    def parameters(self):
        return {
            'path': self.request.path_args,
            'query': self.request.args,
            'header': self.request.headers,
            'cookie': self.request.cookies,
        }

    @property
    def body(self):
        return self.request.data

    @property
    def mimetype(self):
        return self.request.mime_type


class OpenAPIResponse(BaseOpenAPIResponse):

    def __init__(self, response):
        self.response = response

    @property
    def data(self):
        return self.response.data

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def mimetype(self):
        return self.response.content_type
