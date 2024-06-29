"""
Poor WSGI connector for Python

Current Contents:

* headers: Headers
* request: Request and FieldStorage classes, which are used for
  managing requests.
* response: Response classes and functions for creating HTTP responses.
* results: Default result handlers for the connector, such as directory index,
  server errors, or debug output handlers.
* session: Cookie session classes — ``Session`` (plain cookie wrapper) and
  ``PoorSession`` (self-contained encrypted and authenticated dictionary
  cookie; no external dependencies).
* aes_session: ``AESSession`` — stronger self-contained encrypted session
  cookie using AES-256-CTR + HMAC-SHA256 (requires ``pyaes``).
* state: Constants like HTTP status codes and method types.
* wsgi: The Application callable class, which is the main entry point for a
  PoorWSGI web application.
* digest: HTTP Digest Authorization support.
* openapi_wrapper: OpenAPI core wrapper for PoorWSGI Request and Response
  objects.
"""

from poorwsgi.response import abort, make_response, redirect
from poorwsgi.wsgi import Application

__all__ = ["Application", "abort", "make_response", "redirect"]
