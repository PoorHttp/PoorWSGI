"""
Poor WSGI connector for Python

Current Contents:

    #!text
    * request - Headers, Request and FieldStorage classes, which
                is used for managing requests.

    * results - default result handlers of connector like: directory index,
                send_file, SERVER_RETURN, redirect, servers errors or debug
                output handler.

    * session - self-contained cookie based session class

    * state   - constants like http status code, log levels and method types

    * wsgi    - main application function, and functions for working with
                dispatch table
"""

from poorwsgi.request import uni

from poorwsgi.results import redirect, SERVER_RETURN, send_file

from poorwsgi.wsgi import Application

# application callable instance, which is need by wsgi server
application = Application('__poorwsgi__')

# short reference to application instance, which is need by wsgi server
app = application
