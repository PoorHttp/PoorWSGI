"""
Poor WSGI connector for Python

Current Contents:
    
    * request - Headers, Request, FieldStorage and SERVER_RETURN classes, which
                is used for managing requests.

    * results - default result handlers of connector like: directory index,
                send_file, redirect, servers errors or debug output handler.

    * session - self-contained cookie based session class

    * state   - constants like http status code, log levels and method types

    * wsgi    - main application function, and functions for working with
                dispatch table
"""

from request import FieldStorage, SERVER_RETURN

from results import redirect

from state import __author__, __date__, __version__

from wsgi import application, route, set_route, http_state, set_http_state, \
        default, set_default
