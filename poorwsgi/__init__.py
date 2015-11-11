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


__author__ = "Ondrej Tuma (McBig) <mcbig@zeropage.cz>"
__date__ = "11 Nov 2015"
__version__ = "1.6.0dev17"     # https://www.python.org/dev/peps/pep-0386/

# application callable instance, which is need by wsgi server
application = Application('__poorwsgi__')

# short reference to application instance, which is need by wsgi server
app = application
