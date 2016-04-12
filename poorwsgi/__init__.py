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

    * wsgi    - Application callable class, which is the main point for
                poorwsgi web application.
"""

from poorwsgi.request import uni

from poorwsgi.results import redirect, SERVER_RETURN, send_file, send_json

from poorwsgi.wsgi import Application

# Application callable instance, which is need by wsgi server ( *DEPRECATED* )
application = Application('__poorwsgi__')

# Short reference to application instance ( *DEPRECATED* )
app = application
