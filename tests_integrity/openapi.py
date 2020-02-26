"""requests library object Wrapper for openapi_core library objects."""
from urllib.parse import urlparse, parse_qs
from cgi import parse_header

import json

from openapi_core import create_spec
from openapi_core.validation.request.datatypes import \
    RequestParameters
from openapi_core.validation.response.validators import ResponseValidator
from openapi_spec_validator.loaders import ExtendedSafeLoader

import yaml


class OpenAPIRequest():
    """requests.Request wrapper for openapi_core."""

    def __init__(self, request, path_pattern=None):
        self.full_url_pattern = path_pattern or request.url

        self.method = request.method.lower()
        url = urlparse(request.url)
        query = parse_qs(url.query) if url.query else {}
        # when args have one value, that is the value
        args = tuple((key, val[0] if len(val) < 2 else val)
                     for key, val in query.items())

        self.data = request.data

        ctype = parse_header(request.headers.get('Content-Type', ''))
        self.mimetype = ctype[0]

        self.parameters = RequestParameters(
            path=args,
            query=query,
            header=request.headers,
            cookie=request.cookies,
        )


class OpenAPIResponse():

    def __init__(self, response):
        self.response = response
        self.ctype = parse_header(response.headers.get('Content-Type', ''))

    @property
    def data(self):
        return self.response.text

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def mimetype(self):
        return self.ctype[0]


def response_validator_json(filename):
    """Initialization response_validator for openapi.json."""
    with open(filename, "r") as openapi:
        spec = create_spec(json.load(openapi))
        return ResponseValidator(spec)


def response_validator_yaml(filename):
    """Initialization response_validator for openapi.yaml."""
    with open(filename, "r") as openapi:
        spec = create_spec(yaml.load(openapi, ExtendedSafeLoader))
        print("spec:", spec)
        return ResponseValidator(spec)


__all__ = ["response_validator_json", "OpenAPIRequest", "OpenAPIResponse"]
