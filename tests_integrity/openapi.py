"""Requests library object wrapper for openapi_core library objects."""

import json
from email.message import Message
from urllib.parse import parse_qs, urlparse

from openapi_core import Spec  # type: ignore
from openapi_core.validation.request.datatypes import (  # type: ignore
        RequestParameters)


class OpenAPIRequest:
    """A requests.Request wrapper for openapi_core."""

    def __init__(self, request, path_pattern=None):
        self.full_url_pattern = path_pattern or request.url

        self.method = request.method.lower()
        self._url = urlparse(request.url)
        query = parse_qs(self._url.query) if self._url.query else {}
        # when args have one value, that is the value
        args = tuple(
            (key, val[0] if len(val) < 2 else val)
            for key, val in query.items()
        )

        self.request = request
        self.data = request.data

        msg = Message()
        msg["content-type"] = request.headers.get("Content-Type", "")
        self.mimetype = msg.get_content_type()

        self.parameters = RequestParameters(
            path=args,
            query=query,
            header=request.headers,
            cookie=request.cookies,
        )

    @property
    def host_url(self) -> str:
        """Returns the request host URL."""
        return f"{self._url.scheme}://{self._url.netloc}"

    @property
    def path(self) -> str:
        """Returns the request path."""
        assert isinstance(self._url.path, str)
        return self._url.path


class OpenAPIResponse:
    """A requests.Response wrapper for openapi_core."""

    def __init__(self, response):
        self.response = response
        msg = Message()
        msg["content-type"] = response.headers.get("Content-Type", "")
        self.content_type = msg.get_content_type()

    @property
    def data(self):
        """The response body."""
        return self.response.text

    @property
    def status_code(self):
        """The response status code."""
        return self.response.status_code

    @property
    def mimetype(self):
        """The response Content-Type."""
        return self.content_type

    @property
    def headers(self):
        """The response headers."""
        return self.response.headers


def response_spec_json(filename):
    """Initializes a response_validator for openapi.json."""
    with open(filename, "r", encoding="utf-8") as openapi:
        return Spec.from_dict(json.load(openapi))


__all__ = ["OpenAPIRequest", "OpenAPIResponse", "response_spec_json"]
