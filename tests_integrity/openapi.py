"""requests library object Wrapper for openapi_core library objects."""
from urllib.parse import urlparse, parse_qs
from cgi import parse_header

import json

from openapi_core import Spec  # type: ignore
from openapi_core.validation.request.datatypes import (  # type: ignore
    RequestParameters)


class OpenAPIRequest():
    """requests.Request wrapper for openapi_core."""

    def __init__(self, request, path_pattern=None):
        self.full_url_pattern = path_pattern or request.url

        self.method = request.method.lower()
        self._url = urlparse(request.url)
        query = parse_qs(self._url.query) if self._url.query else {}
        # when args have one value, that is the value
        args = tuple((key, val[0] if len(val) < 2 else val)
                     for key, val in query.items())

        self.request = request
        self.data = request.data

        ctype = parse_header(request.headers.get('Content-Type', ''))
        self.mimetype = ctype[0]

        self.parameters = RequestParameters(
            path=args,
            query=query,
            header=request.headers,
            cookie=request.cookies,
        )

    @property
    def host_url(self) -> str:
        """Return request host url."""
        return f"{self._url.scheme}://{self._url.netloc}"

    @property
    def path(self) -> str:
        """Return request path."""
        assert isinstance(self._url.path, str)
        return self._url.path


class OpenAPIResponse():
    """requests.Response wrapper for openapi_core."""

    def __init__(self, response):
        self.response = response
        self.ctype = parse_header(response.headers.get('Content-Type', ''))

    @property
    def data(self):
        """Response body"""
        return self.response.text

    @property
    def status_code(self):
        """Response status_code"""
        return self.response.status_code

    @property
    def mimetype(self):
        """Response Content-Type"""
        return self.ctype[0]

    @property
    def headers(self):
        """Response Headers"""
        return self.response.headers


def response_spec_json(filename):
    """Initialization response_validator for openapi.json."""
    with open(filename, "r", encoding="utf-8") as openapi:
        return Spec.from_dict(json.load(openapi))


__all__ = ["response_spec_json", "OpenAPIRequest", "OpenAPIResponse"]
