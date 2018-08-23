"""
Poor WSGI connector for Python

Current Contents:

* request - Headers, Request and FieldStorage classes, which
            is used for managing requests.
* results - default result handlers of connector like: directory index,
            send_file, SERVER_RETURN, redirect, servers errors or debug
            output handler.
* session - self-contained cookie based session class
* state   - constants like http status code, log levels and method types
* wsgi    - Application callable class, which is the main point for
            poorwsgi web application.
"""

from poorwsgi.response import redirect, abort

from poorwsgi.wsgi import Application

__all__ = ["Application", "redirect", "abort"]
