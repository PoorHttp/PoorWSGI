PoorWSGI Architecture
=======================

This document describes the internal architecture of the PoorWSGI framework. It is intended for developers who want to understand how the framework works, extend its functionality, or contribute to its development.

Project Philosophy
------------------
PoorWSGI is designed as a minimalist, lightweight, and extensible WSGI framework. Its core philosophy is to provide a solid foundation for web applications and APIs without imposing a rigid structure or including unnecessary components. The design prioritizes simplicity, developer convenience, and clear, straightforward code.

Key principles:

*   **Minimalism**: The core is small and has few dependencies.
*   **Explicitness**: The request-response cycle is easy to follow.
*   **Extensibility**: The framework provides clear extension points, such as middleware-like hooks and customizable objects.
*   **Developer-Friendly Debugging**: In debug mode, the framework offers powerful introspection tools.

Core Objects
------------
The framework's functionality is built around a few central objects.

`Application` (`poorwsgi/wsgi.py`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the heart of the framework. An instance of the `Application` class is the main entry point for the WSGI server. Its primary responsibilities are:

*   **Configuration**: Storing all application settings.
*   **Routing**: Managing a routing table that maps URL paths and HTTP methods to handler functions.
*   **Request Lifecycle**: Orchestrating the entire process of handling a request from start to finish.
*   **Hooks**: Managing `before_response` and `after_response` hooks, which act as a simple middleware system.

`Request` (`poorwsgi/request.py`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This object encapsulates all data from an incoming HTTP request. It is created by the `Application` object for each request. Key features include:

*   **Automatic Parsing**: It automatically parses query strings (`req.args`), form data (`req.form`), and JSON bodies (`req.json`) based on the request's `Content-Type` header and application configuration. This simplifies data access within handlers.
*   **Header Access**: Provides easy access to request headers via `req.headers`.
*   **Extensibility**: The `Request` object can be easily extended with custom data, for example, by attaching a user object (`req.user`) or a database session (`req.db`) within a `before_response` hook.

`Response` & `HTTPException` (`poorwsgi/response.py`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module defines how outgoing responses are constructed.

*   `BaseResponse` is the base class for all response objects. Its children, like `Response`, `JSONResponse`, and `FileResponse`, handle different types of content.
*   The `make_response` factory function is a crucial component. It intelligently converts a handler's return value (e.g., a `str`, `dict`, or `int` status code) into a complete `Response` object. This allows handlers to be very simple.
*   `HTTPException` is the standard way to handle errors. Calling `abort(404)` or raising an `HTTPException` subclass will interrupt the normal flow and immediately send an error response.

`results` (`poorwsgi/results.py`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module contains pre-defined handlers for all standard HTTP status codes (e.g., `not_found` for 404, `internal_server_error` for 500).

*   These are used as default error handlers if the user does not register their own.
*   It also contains the powerful `debug_info` handler, which generates a comprehensive introspection page at the `/_debug-info` URL when the application is in debug mode.

The Request-Response Lifecycle
------------------------------
The core logic of the framework is the request lifecycle, which follows these steps:

1.  A WSGI server receives an HTTP request and calls the `Application` instance.
2.  The `Application.__call__` method wraps the main logic in a `try...except` block to catch `HTTPException` and other errors.
3.  The primary `Application.__request__` method is executed.
4.  An instance of the `Request` class is created from the WSGI `environ` dictionary.
5.  The routing system (`handler_from_table`) is used to find the appropriate handler function based on the request's path and method. If no handler is found, a 404 error is triggered.
6.  All registered `before_response` hooks are executed in sequence. These hooks can modify the `Request` object (e.g., by adding a user session) or even short-circuit the request by returning a `Response`.
7.  The selected handler function is called with the `Request` object as its argument (`handler(req)`).
8.  The return value from the handler is passed to the `make_response` factory to create a valid `Response` object.
9.  All registered `after_response` hooks are executed. They can modify the final `Response` object (e.g., by adding custom headers).
10. The `Response` object is used to call the `start_response` callable and return the response body as an iterable, fulfilling the WSGI specification.

Routing
-------
URL routing is primarily managed via the `@app.route` decorator:

.. code-block:: python

    from poorwsgi import Application, state

    app = Application()

    @app.route('/', state.GET|state.POST)
    def index(req):
        return "Hello, World!"

The decorator adds the function to the application's internal routing table. The router matches the request path and HTTP method to find the correct handler to execute. It supports both static paths and paths with variable placeholders.

Extending PoorWSGI
------------------
The framework is designed to be easily extended. Here are some common ways to do so:

*   **Middleware via Hooks**: The `before_response` and `after_response` hooks are the primary way to implement middleware. Use `before_response` for tasks like authentication, database session management, or request logging. Use `after_response` for modifying headers or response content.
*   **Custom Error Handlers**: You can replace the default error pages by registering your own handlers for specific HTTP status codes using `@app.error_handler(404)`.
*   **Custom `Request` Attributes**: Attach any data you need to the `Request` object within a hook for easy access in your handlers (e.g., `req.session = get_session(...)`).
*   **Custom `Response` Types**: For specialized content types, you can create a subclass of `poorwsgi.response.BaseResponse` and return an instance of it from your handlers.

Project Structure
-----------------

*   `poorwsgi/`: The main package directory containing the framework's source code.
*   `tests/`: Contains unit tests that test individual components of the framework in isolation.
*   `tests_integrity/`: Contains integration tests that verify the behavior of the complete application, often by running servers from the `examples/` directory.
*   `examples/`: A collection of sample applications demonstrating various features of the framework.
