"""
Poor WSGI connector for Python

Current Contents:

* request: Headers, Request and FieldStorage classes, which is used for
  managing requests.
* response: Response classes and some make responses functions for creating
  request response.
* results: default result handlers of connector like directory index,
  servers errors or debug output handler.
* session: self-contained cookie based session class
* state: constants like http status code and method types
* wsgi: Application callable class, which is the main point for poorwsgi web
  application.
* digest: HTTP Digest Authorization support.
* openapi_wrapper: OpenAPI core wrapper for PoorWSGI Request and Response
  object
"""

from poorwsgi.response import redirect, abort, make_response

from poorwsgi.wsgi import Application

__all__ = ["Application", "redirect", "abort", "make_response"]
