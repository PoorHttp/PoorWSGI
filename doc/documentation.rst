Responses
---------
The main goal of all WSGI middleware is to return a response corresponding to an HTTP
or WSGI request. Responding in PoorWSGI is just like other known frameworks.

Returning values
~~~~~~~~~~~~~~~~

Just value
``````````
The easiest way is to return a string or bytes. String values are automatically
converted to bytes, because it is WSGI internal. The HTTP Response is 200 OK with
``text/html; charset=utf-8`` content type and a default X-Powered-By header.

.. code:: python

   @app.route('/some/path')
   def some_path(req):
      return 'This is content for some path'

These examples return the same values.

.. code:: python

   @app.route('/other/path')
   def some_path(req):
      return b'This is content for some path'

Generator
`````````
The second way is to return a generator. You can return any iterable object, but it must
always be the first parameter; specifically, it cannot be a tuple!
*See Returned parameters*. A generator must always return bytes!

.. code:: python

    @app.route('/list/of/bytes')
    def list_of_bytes(req):
        return [b'Hello ',
                b'world!']

Or you can return any function that is a generator.

.. code:: python

    @app.route('/generator/of/bytes')
    def generator_of_bytes(req):
        def generator():
            for i in range(10):
                yield b'%d -> %x\n' % (i, i)
        return generator()

Or the handler could be a generator.

.. code:: python

    @app.route('/generator/of/bytes')
    def generator_of_bytes(req):
        for i in range(10):
            yield b'%d -> %x\n' % (i, i)

Returned parameters
```````````````````
In fact, you can return more than one value. You can return the content type,
headers, and status code as additional parameters. Python returns all parameters
as one tuple. There is no need to wrap them in brackets.

.. code:: python

    @app.route('/text/message')
    def text_message(req):
        return "Hello world!", "text/plain"

The first argument can still be a generator.

.. code:: python

    @app.route('/generator/of/bytes')
    def generator_of_bytes(req):
        def generator():
            for i in range(10):
                yield b'%d -> %x\n' % (i, i)
        return generator(), "text/plain", ()    # empty headers

All values could look like this:

.. code:: python

    @app.route('/hello')
    def hello(req):
        return "Hello world!", "text/plain", ('X-Attribute', 'hello world'),
               HTTP_OK

Returning Responses
~~~~~~~~~~~~~~~~~~~

make response
`````````````
Response is the base class for returning values. In fact, other values which are
returned from request handlers are converted to a Response object via the
make_response function.

.. code:: python

    def make_response(data, content_type="text/html; character=utf-8",
                      headers=None, status_code=HTTP_OK)


data : str, bytes, dict, list, None or generator
    Returned value as response body. Each type of data returns a different
    response type:

        - str, bytes - Response
        - dict, list - JSONResponse
        - None - NoContentReponse
        - generator - GeneratorResponse

content_type : str
    The ``Content-Type`` header is set if this header is not already set
    in the headers.
headers : Headers, tuple, dict, ...
    If it is a Headers instance, it will be set *(e.g., referer)*. Other types
    are sent to the Headers constructor.
status_code : int
    HTTP status code, HTTP_OK is 200.

You can use the headers parameter instead of the `content_type` argument.

.. code:: python

    @app.http_state(NOT_FOUND)
    def not_found(req, *_):
        return make_response(b'Page not Found',
                             headers={"Content-Type": "text/plain"},
                             status_code=NOT_FOUND)

If you return just a simple type, or a tuple of arguments, PoorWSGI automatically
calls the make_response function to create a response for you.

.. code:: python

    @app.route("/json")
    def not_found(req):
        """Return JSONResponse"""
        return {"msg": "Message", "type": "object"}


    @app.route('/gone')
    def gone(req):
        """Return NoContentResponse"""
        return None, "", None, HTTP_GONE


Response
````````
A Response object is one of the basic elements of a WSGI application. Response is
an object that contains all the necessary data to return a valid HTTP answer to
the client: status code, text reason for the status code, headers, and body.
That's all. All values returned from handlers are transformed to a Response
object if possible. If a handler returns a valid Response, it will be returned
as-is.

Response has some useful functionality, such as the write method for appending
to the body with auto-counting of ``Content-Length``, and additional header
management.

.. code:: python

    @app.route('/teapot')
    def teapot(req):
        return Response("I'm teapot :-)", content_type="text/plain",
                        status_code=418)

There are some additional subclasses with specific functionality.

JSONResponse
````````````
There is a JSONResponse class for quickly returning JSON.

.. code:: python

    @app.route('/json')
    def teapot(req):
        return JSONReponse(status_code=418, message="I'm teapot :-)",
                           numbers=list(range(5)))

This response returns the following data with status code 418:

.. code:: json

    {
        "message": "I\'m teapot :-)",
        "numbers": [0, 1, 2, 3, 4]
    }

Or you can simply return a dictionary or a list. It will be automatically
converted to JSONResponse by the make_response function. So it is similar to
returning text or bytes.

Be careful that your dict or list **has to be convertible** to JSON by the
json.dumps function.

.. code:: python

    @app.route('/dict')
    def get_dict(_):
        """Return dictionary"""
        return {"route": "/dict", "type": "dict"}

    @app.route('/list')
    def get_list(_):
        """Return list"""
        return [["key", "value"], ["route", "/list"], ["type", "list"]]



JSONGeneratorResponse
`````````````````````
There is also a JSONGeneratorResponse class, which can return JSON and
can accept generators as arrays. This response is streamed like GeneratorResponse,
so data is not buffered in memory if the WSGI server does not buffer it.

.. code:: python

    @app.route('/json-generator')
    def teapot(req):
        return JSONGeneratorReponse(status_code=418, message="I'm teapot :-)",
                                    numbers=range(5))

This response returns the following data with status code 418:

.. code:: json

    {
        "message": "I\'m teapot :-)",
        "numbers": [0, 1, 2, 3, 4]
    }

FileResponse
````````````
FileResponse opens the file and sends it through ``wsgi.filewrapper``, which
could be a *sendfile()* call. See PEP 3333. Content type and length are read
from the system.

.. code:: python

    @app.route('/favicon.ico')
    def favicon(req):
        return FileResponse("/favicon.ico")

GeneratorResponse
`````````````````
A Response that is used for generator values. A generator **must** return bytes,
not strings. For a generator that returns strings, use **StrGeneratorResponse**,
which encodes the strings to UTF-8 bytes.

NoContentResponse
`````````````````
Sometimes you don't want a response payload. NoContentResponse has a default
code of `204 No Content`.

RedirectResponse
````````````````
A Response with an interface for a more comfortable redirect response.

.. code:: python

    @app.route("/old/url")
    def old_url(req):
        return RedirectResponse("/new/url", True)

NotModifiedResponse
```````````````````
NotModifiedResponse is based on NoContentResponse with status code
`304 Not Modified`. You have to add a Not Modified header in the headers
parameters or as a constructor argument.

.. code:: python

    from base64 import urlsafe_b64encode
    from hashlib import md5

    @app.route("/static/filename")
    def static_url(req):
        last_modified = int(getctime(req.document_root+"/filename"))
        weak = urlsafe_b64encode(md5(last_modified.to_bytes(4, "big")).digest())
        etag = f'W/"{weak.decode()}"'

        if 'If-None-Match' in req.headers:
            if  etag == req.headers.get('If-None-Match'):
                return NotModifiedResponse(etag=etag)

        if 'If-Modified-Since' in req.headers:
            if_modified = http_to_time(req.headers.get('If-Modified-Since'))
            if last_modified <= if_modified:
                return NotModifiedResponse(date=time_to_http())

        return FileResponse(req.document_root+"/filename",
                            headers={'ETag': etag})

Partial Content
```````````````
Sometimes, you want to return partial content, which is a typical reaction to
`Range` headers. For such situations, there are the `parse_range` function and
the `make_partial` Response method.

.. code:: python

    @app.route("/last/100/bytes")
    def last_bytes(req):
        response = Response(os.urandom(1000))
        response.make_partial({None, 100})
        return response


    @app.route("/var/log/messages")
    def messages(req):
        """Return parts defined in request Range header."""
        response = FileResponse("/var/log/messages")
        if 'Range' in req.headers:
            ranges = parse_range(req.headers['Range'])
            if "bytes" in ranges:
                response.make_partial(ranges["bytes"])
        return response

PartialResponse
```````````````
For special use cases where a programmer has their own mechanism to select a range,
for example if units are not bytes, there is PartialResponse, which is similar
to Response, but is already set to ``206 Partial Content``, and you only need to
use the ``make_range`` method to create the correct ``Content-Range`` header.

.. code:: python

    @app.route("/some/range"):
    def some_range(req):
        """Return 100 unicodes with right Content-Range header."""
        response = PartialResponse(''.join(random.choices("ěščřžýáíé", k=100)))
        response.make_range({100, 199}, "unicodes", 200)
        return response

Stopping handlers
~~~~~~~~~~~~~~~~~

HTTPException
`````````````
There is the HTTPException class, based on Exception, which is used for stopping
a handler with the correct HTTP status. There are two possible scenarios:

You want to stop with a specific HTTP status code, and a handler from
the application will be used to generate the correct response.

.. code:: python

    @app.route("/some/url")
    def some_url(req):
        if req.is_xhr:
            raise HTTPException(HTTP_BAD_REQUEST)
        return "Some message", "text/plain"

Or you want to stop with a specific response. Instead of a status code, just
use Response object.

.. code:: python

    @app.route("/other/url")
    def some_url(req):
        if req.is_xhr:
            error = Response(b'{"reason": "Ajax not suported"}',
                             content_type="application/json",
                             status_code=HTTP_BAD_REQUEST)
            raise HTTPException(error)
        return "Other message", "text/plain"

**Additional functionality**

If the status code is ``DECLINED``, it returns nothing. That means no status
code, no headers, no response body. Just stop the request.

If the status code is ``HTTP_NO_CONTENT``, it returns NoContentResponse, so the
message body is not sent.

When the handler raises any other exception, it generates an Internal Server
Error status code.

Compatibility
`````````````
For compatibility with old PoorWSGI and other WSGI middleware, there are two
functions.

**redirect**

It has the same interface as RedirectResponse, and only raises the HTTPException
with RedirectResponse.

**abort**

It has the same interface as HTTPException, and voila, it raises the HTTPException.

Routing
-------

There are two ways to set a path handler: via decorators of the Application object,
or using a set\_ method where one of the parameters is your handler. The choice
depends on how your application is structured. If your web project has one or a few
files where your handlers are, it is a good idea to use decorators. But if you
have a large project with many files, it could be difficult to load all files with
decorated handlers. In that case, set\_ methods in a single file, such as a
route file or dispatch table, is a better approach.

Static Routing
~~~~~~~~~~~~~~
There is a method and a decorator to set your function (handler) to respond to a
static route: Application.set_route and Application.route. Both of them have
two parameters: first, the required path like ``/some/path/for/you``, and second,
method flags, which default to METHOD_HEAD | METHOD_GET. There are other
methods in the state module like METHOD_POST, METHOD_PUT, etc. There are two
special constants: METHOD_GET_POST, which is HEAD | GET | POST, and METHOD_ALL,
which includes all supported methods. If the method does not match but the path
exists in the internal table, the HTTP state HTTP_METHOD_NOT_ALLOWED is
returned.

.. code:: python

    @app.route('/some/path')
    def some_path(req):
        return 'Data of some path'

    def other_path(req):
        return 'Data of other path'
    app.set_route('/some/other/path', other_path, state.METHOD_GET_POST)

You can pop from the application table via method Application.pop_route, or get
the internal table via Application.routes property. **Each path can have only
one handler**, but one handler can be used for more paths.

Regular expression routes
~~~~~~~~~~~~~~~~~~~~~~~~~
As in other WSGI connectors (or frameworks, if you prefer), there is a way to
define routes that capture part of the URL path as a parameter of the handler.
PoorWSGI calls them **regular expression routes**. You can use them in a nice
human-readable form or in your own regular expressions. Basic use is defined by
group name.

.. code:: python

    # group regular expression
    @app.route('/user/<name>')
    def user_detail(req, name):
        return 'Name is %s' % name

Filters are defined by regular expressions from the Application.filters table.
Each filter is used to transform a URL group into a regular expression. The default
filter is ``r'[^/]+'`` with a ``str`` convert function. You can use any filter
from the filters table.

.. code:: python

    # group regular expression with filter
    @app.route('/<surname:word>/<age:int>')
    def surnames_by_age(req, surname, age):
        return 'Surname is: %s and age is: %d' % (surname, age)

The :int filter is defined by ``r'-?\d+'`` with the ``int`` conversion function.
So age must be a number and the input parameter is an ``int`` instance.

There are predefined filters, for example: **:int**, **:word**, **:re:**, and
**none** as the default filter. :word is defined as the ``r'\w+'`` regular
expression, and PoorWSGI uses the ``re.U`` flag, so it matches any Unicode string
(i.e., UTF-8 string). For all filters, see the Application.filters property or
the ``/debug-info`` page.

You can get a copy of the filters table by calling the Application.filters
property. This filters table is output to the debug-info page. Adding your own
filter is possible with the ``set_filter`` function, which takes a name, a
regular expression, and a convert function (which is ``str`` by default). You can
then use this filter in a group regular expression.

.. code:: python

    app.set_filter('email', r'[a-zA-Z\.\-]+@[a-zA-Z\.\-]+', str)

    @app.route('/user/<login:email>')
    def user_by_login(req, login):
        return 'Users email is %s' % login

Alternatively, you can use filters defined by inline regular expressions. That is
the ``:re:`` filter. This filter takes a regular expression that you provide, and
always uses the ``str`` convert function, so the parameter is always a string.

.. code:: python

    @app.route('/<number:re:[a-fA-F\d]+>')
    def hex_number(req, number):
        return ('Number is %s that is %d so %x' %
                (number, int(number,16), int(number,16)))

Group naming
~~~~~~~~~~~~
Group names **must be unique** in the defined path. They are stored in an
ordered dictionary and wrapped by their convert functions. You can name them
in the route definition as you wish; they do not need to match the parameter
names in the handler, but they must maintain the same ordering. Be careful not to
name parameters in the handler with a Python keyword, like ``class`` for example. If
you prefer, you can use Python's "varargs" syntax to receive any number of parameters
in your handler function.

.. code:: python

    @app.route('/test/<variable0>/<variable1>/<variable2>')
    def test_varargs(req, *args):
        return "Parse %d parameters %s" % (len(args), str(args))

A future feature of regular expression routes is direct access to the dictionary
with the ``req.groups`` variable. This variable is set from any regular
expression route.

.. code:: python

    @app.route('/test/<variable0>/<variable1>/<variable2>')
    def test_varargs(req, *args):
        return "All input variables from url path: %s" % str(req.groups)

Regular expression routes, like static routes, can be set with Application.route
or Application.set_route methods. Internally, however, Application.regular_route
or Application.set_regular_route is called. The same situation applies to
Application.pop_route and Application.pop_regular_route.

Other handlers
--------------

Default handler
~~~~~~~~~~~~~~~
If no route matches, two scenarios can occur. The first is to call the default
handler if the method matches. The default handler is set with the default
Application decorator or Application.set_default method. The parameter is only
the method, which also defaults to METHOD_HEAD | METHOD_GET. Unlike route
handlers, when the method does not match, a 404 error is returned.

So the default handler is a fallback with the ``r'/.*'`` regular expression. For
example, you can use it for any OPTIONS method.

.. code:: python

    @app.default(METHOD_OPTIONS):
    def default(req):
        return b'', '', {'Allow': 'OPTIONS', 'GET', 'HEAD'}

Be careful: the default handler is called before the 404 not found handler. If it
is possible to serve the request in any other way, it will be. For example, if
poor_DocumentRoot is set and PoorWSGI finds the file, it will be sent. Of
course, the internal file or directory handler is used only with METHOD_GET or
METHOD_HEAD.

HTTP state handlers
~~~~~~~~~~~~~~~~~~~
There are some predefined HTTP state handlers, which are used when other HTTP
states are raised via HTTPException or any other exception that ends with an
HTTP_INTERNAL_SERVER_ERROR status code.

You can define your own handlers for any combination of status code and method
type, similar to route handlers. Responses from these handlers are the same as
in route handlers.

Note that some HTTP state handlers receive additional keyword arguments.

.. code:: python

    @app.http_state(state.HTTP_NOT_FOUND)
    def page_not_found(req, *_):
        return "Your request %s not found." % req.path, "text/plain"

If your HTTP state (error) handler raises an error, a 500 Internal Server Error
is returned and the default internal server error handler is called. If your
default internal server error handler crashes as well, the built-in PoorWSGI
internal server error handler is called.

Error handlers
~~~~~~~~~~~~~~
In most cases, when an exception is raised from your handler, *Internal Server
Error* is returned from the server. When you want to handle each type of
exception, you can define your own error handler, which will be called instead
of the HTTP_INTERNAL_SERVER_ERROR state handler.

.. code:: python

    class MyValueError(ValueError)
        pass


    @app.error_handler(ValueError)
    def value_error(req, error):
        """This is called when value error was raised."""
        return "Value Error: %s" % error, state.HTTP_BAD_REQUEST


    @app.route('/value/<value:int>')
    def value_handler(req, value)
        if value != 42:
            raise MyValueError("Not a valid value")
        return "Yep!"


Exception handlers are stored in an OrderedDict, so the exception type is
checked in the same order as you set error handlers. Therefore, you must define
the handler for the base exception last.

Before and After response
~~~~~~~~~~~~~~~~~~~~~~~~~

PoorWSGI also has two special lists of handlers. The first iterates and calls
before each response. You can add functions with Application.before_response and
Application.after_response decorators or Application.add_before_response and
Application.add_after_response methods. There are also
Application.pop_before_response and Application.pop_after_response methods to
remove handlers.

Before response handlers are called in the order they were added to the list.
Their return values are ignored. If they raise an error, an Internal Server Error
is returned and the HTTP state handler is called.

After response handlers are called in the order they were added to the list. If
they raise an error, an Internal Server Error is returned and the HTTP state
handler is called, but all code from the before response list and from the
route handler has already been executed.

An after response handler is called even if an error handler, such as
internal_server_error, was called.

A before response handler must have a request argument, but an after response
handler must have request and response arguments.

.. code:: python

    @app.before_response()
    def before_each_response(request):
        ...

    @app.after_response()
    def after_each_response(request, response):
        ...


Filtering
`````````

TODO: How to write an output filter, gzip for example...

WebSockets
~~~~~~~~~~

WebSockets are not directly supported in PoorWSGI, but upgrade requests can be
handled like other HTTP requests. See the
`websocket.py <https://github.com/PoorHttp/PoorWSGI/blob/master/examples/websocket.py>`_
example, which uses the uWSGI implementation or WSocket implementation.


Request variables
-----------------
PoorWSGI has two classes for parsing request arguments: one for arguments from
the request path (typical for GET requests) and one for arguments from the request
body (typical for POST requests). This parsing is enabled by default, but you can
configure it with options.

Query arguments
~~~~~~~~~~~~~~~
Request query arguments are stored in the Args class, defined in the
poorwsgi.request module. Args is a dict-based class with the getfirst and
getlist methods. You can access query variables via ``req.args`` whenever
poor_AutoArgs is set to On, which is the default.

.. code:: python

    @app.route('/test/get')
    def test_get(req)
        name = req.args.getfirst('name')
        colors = req.args.getlist('color', func=int)
        return "Get arguments are %s" % str(req.args)

If no arguments are parsed, or if poor_AutoArgs is set to Off, req.args is an
EmptyForm instance, which is also a dict-based class with both methods.

Form arguments
~~~~~~~~~~~~~~
Request form arguments are stored in the FieldStorage class, defined in the
poorwsgi.fieldstorage module. This class is inspired by FieldStorage from the
legacy cgi module. Variables are parsed whenever poor_AutoForm is set to
On (which is the default), the request method is POST, PUT or PATCH, and the
request MIME type is one of `Application.form_mime_types`. You can also trigger
this parsing for other methods, but ``wsgi.input`` must exist in the request
environment from the WSGI server.

The ``req.form`` instance is created with poor_KeepBlankValues and
poor_StrictParsing variables, just as the Args class is created. However,
FieldStorageParser has a ``file_callback`` variable, which is configurable by the
Application.file_callback property.

.. code:: python

    @app.route('/test/post', methods = state.METHOD_GET_POST)
    def test_post(req)
        id = req.args.getfirst('id', 0, int) # id is get from request uri and it
                                             # is convert to number with zero
                                             # as default
        name = req.form.getfirst('name')
        colors = req.form.getlist('color', func=int)
        return "Post arguments for id are %s" % (id, str(req.args))

Similar to the Args class, if poor_AutoForm is set to Off, or if the method is
not POST, PUT or PATCH, ``req.form`` is an EmptyForm instance instead of
FieldStorage.

JSON request
~~~~~~~~~~~~
Initially, JSON requests came from AJAX. There is automatic JSON parsing in the
Request object, which parses the request body to a JSON variable. This parsing
starts only when the Application.auto_json variable is set to True (default) and
the MIME type of a POST, PUT or PATCH request is application/json. Then the
request body is parsed to the json property. You can configure JSON types via the
Application.json_mime_types property, which is a list of request MIME types.

.. code:: python

    import json

    @app.route('/test/json',
               methods=state.METHOD_POST | state.METHOD_PUT | state.METHOD_PATCH)
    def test_json(req):
        for key, val in req.json.items():
            req.error_log('%s: %s' % (key, str(val)))

        res = Response(content_type='application/json')
        json.dump(res, {'Status': '200', 'Message': 'Ok'})
        return res

JQuery AJAX request could look like this:

.. code:: js

    $.ajax({ url: '/test/json',
             type: 'put',
             accepts : {json: 'application/json', html: 'text/html'},
             contentType: 'application/json',
             dataType: 'json',
             data: JSON.stringify({'test': 'Test message',
                                   'count': 42, 'note': null}),
             success: function(data){
                console.log(data);
             },
             error: function(xhr, status, http_status){
                    console.error(status);
                    console.error(http_status);
             }
    });

There are a few variants that req.json could be:

* JsonDict when a dictionary is parsed.
* JsonList when a list is parsed.
* Other base types from the json.loads function, such as str, int, float, bool,
  or None.
* None when JSON parsing fails. This is logged with a WARNING log level.

File uploading
~~~~~~~~~~~~~~
By default, FieldStorage stores files somewhere in the ``/tmp`` directory. This
happens in FieldStorageParser, which calls ``TemporaryFile``. Uploaded files
are accessible like other form variables, but:

Any variable from FieldStorage is accessible with the ``__getitem__`` method. So
you can get a variable by ``req.form[key]``, which returns a FieldStorage
instance. This instance has some attributes that you can use to test what type
of variable it is.

.. code:: python

    @app.route('/test/upload', methods = state.METHOD_GET_POST)
    def test_upload(req):
        # store file from upload variable to my_file_storage file
        if 'upload' in req.form and req.form['upload'].filename:
            with open('my_file_storage', 'w+b') as f:
                f.write(req.form['upload'].file.read())

Own file callback
~~~~~~~~~~~~~~~~~
Sometimes, you want to use your own file_callback because you don't want to use
TemporaryFile as storage for uploaded files. You can do it by simply adding a
class that is an ``io.FileIO`` class in Python 3.x. Then, only set the
Application.file_callback property.

.. code:: python

    from poorwsgi import Application
    from io import FileIO

    app = Application('test')
    app.file_callback = FileIO

As you can see, this example works, but it is a poor solution to your problem.
A better solution is to store files only if they do not already exist, in a
configurable directory. You need to use a factory to create file_callback. The
following example shows custom form processing; however, this is not necessary
since ``file_callback`` can be set directly via an Application property.

.. code:: python

    from io import FileIO
    from os.path import exists

    from poorwsgi import Application, state, fieldstorage

    app = Application('test')


    class Storage(FileIO):
        def __init__(self, directory, filename):
            self.path = directory + '/' + filename
            if exists(self.path):
                raise Exception("File %s exist yet" % filename)
            super(Storage, self).__init__(self.path, 'w+b')

    class StorageFactory:
        def __init__(self, directory):
            self.directory = directory
            if not exists(directory):
                os.mkdir(directory)

        def create(self, filename):
            return Storage(self.directory, filename)

    # disable automatic request body parsing - IMPORTANT !
    app.auto_form = False

    @app.before_response()
    def auto_form(req):
        """ Own implementation of req.form paring before any POST response
            with own file_callback.
        """
        if req.method_number == state.METHOD_POST:
            factory = StorageFactory('./upload')
            try:
                parser = FieldStorageParser(
                    req.input, req.heades,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing,
                    file_callback=factory.create)
                req.form = parser.parser()
            except Exception as e:
                req.log_error(e)

CachedInput
~~~~~~~~~~~

When HTTP forms are base64 encoded, FieldStorageParser uses readline on the
request input file. This is not optimal. CachedInput is a class that serves as
a wrapper around the ``wsgi.input`` file to address this.

Process variables
~~~~~~~~~~~~~~~~~~
Here are the application variables used to configure request processing.


Application.auto_args
`````````````````````
If ``auto_args`` is set to ``True`` (which is the default), the Request object
parses input arguments from the request URI at initialization. There will be a
``Request.args`` property, which is an instance of the ``Args`` class. If you want
to disable this functionality, set this property to ``False``. If argument
parsing is disabled, ``Request.args`` will be an instance of ``EmptyForm`` with
the same interface and no data.

Application.auto_form
`````````````````````
If ``auto_form`` is set to ``True`` (which is the default), the Request object
parses input arguments from the request body at initialization when the request
type is POST, PUT or PATCH. There will be a ``Request.form`` property which is
an instance of the ``FieldStorage`` class. If you want to disable this
functionality, set this property to ``False``. If form parsing is disabled, or
JSON is detected, ``Request.form`` will be an instance of ``EmptyForm`` with the
same interface and no data.

Application.form_mime_types
``````````````````````````````
List of MIME types, which is parsed as an input form by the
``FieldStorageParser`` class. If the input request does not have one of these
MIME types set, that form will not be parsed.

Application.file_callback
`````````````````````````
A class or function that is used to store a file from the form. See
`own file callback`_ for more details.

Application.auto_json
`````````````````````
If it is ``True`` (which is the default), the method is POST, PUT or PATCH and
the request mime type is JSON, then the Request object automatically parses
the request body to the ``Request.json`` dict property. If it is disabled, or if
a form is detected, then an ``EmptyForm`` instance is set.

Application.json_mime_types
``````````````````````````````
List of MIME types, which is parsed as JSON by the ``json.loads`` function.
If the input request does not have one of these MIME types set, then
``Request.json`` will not be parsed.

Application.keep_blank_values
`````````````````````````````
This property is passed to the Args and FieldStorageParser classes when
``auto_args`` and ``auto_form`` are set, respectively.
By default, this property is set to ``0``. If it is set to ``1``, blank values
will be interpreted as empty strings.

Application.strict_parsing
``````````````````````````
This property is passed to the Args and FieldStorageParser classes when
``auto_args`` and ``auto_form`` are set, respectively.
By default, this variable is set to ``0``. If it is set to ``1``, a ValueError
exception may be raised on a parsing error. You will almost certainly never want to
set this variable to ``1``; if you do, use it in your own parsing.

.. code:: python

    app.auto_form = False
    app.auto_args = False
    app.strict_parsing = 1

    @app.before_response()
    def auto_form_and_args(req):
        """ This is own implementation of req.form and req.args paring """
        try:
            req.args = request.Args(req,
                                    keep_blank_values=app.keep_blank_values,
                                    strict_parsing=app.strict_parsing)
        except Exception as e:
            loging.error("Bad request uri: %s", e)

        if req.method_number == state.METHOD_POST:
            try:
                parser = fieldstorage.FieldStorageParser(
                    req.input, req.headers,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing)
                req.form = parser.parse()
            except Exception as e:
                logging.error("Bad request body: %s", e)

Application.auto_cookies
````````````````````````
When ``auto_cookies`` is set to ``True`` (which is the default), the
``Request.cookies`` property is set when the request headers contain a ``Cookie``
header. Otherwise, an empty tuple will be set.


Application / User options
--------------------------
Like mod_python's Request, the PoorWSGI Application has a get_options method.
This method returns a dictionary of application options, whose names start with
the ``app_`` prefix. This prefix is stripped from the option names.

.. code:: ini

    [uwsgi]                                         # uwsgi config example
    ...
    env = app_db_file = mywebapp.db                 # variable is db_file
    env = app_tmp_path = tmp                        # variable is tmp_path
    env = app_templ = templ                         # variable is templ

And you can get these variables with get_options method:

.. code:: python

    config = app.get_options()

    @app.route('/options')
    def list_options(req):
        return ("%s = %s" % (key, val) in config.items())

The output of application URL /options looks like this:

::

    db_file = mywebapp.db
    tmp_path = tmp
    templ = templ

You can also store your variables in the request object. There are a few reserved
variables for you, which PoorWSGI never uses, and which are ``None`` by default:

:req.user:   For user object, who is login, check_digest decorator set this
             variable.
:req.api:    For API checking. OpenAPIRequest use this variable.
:req.db:     For a single database connection per request. You can store a
             structure with multiple databases if needed.
:req.app\_:  As a prefix for any of your application variables.

So if you want to add any other variable, be careful how you name it.

Headers and Sessions
--------------------
Request Headers
~~~~~~~~~~~~~~~
Request headers were introduced earlier; this section provides more detail.
The Request object has a ``headers_in`` attribute, which
is an instance of ``wsgiref.headers.Headers``. These headers contain the request
headers from the client, similar to mod_python. You can read them as needed.

In addition, there are some Request properties for accessing parsed header values.

:headers:           Full headers object.
:mime_type:         Return mime type part from ``Content-Type`` header
:charset:           Return charset part from ``Content-Type`` header
:content_length:    Return content length if ``Content-Length`` header is set,
                    or -1 if not.
:accept:            List of ``Accept`` content negotiations set.
:accept_charset:    List of ``Accept-Charset`` content negotiations set.
:accept_encoding:   List of ``Accept-Encoding`` content negotiations set.
:accept_language:   List of ``Accept-Language`` content negotiations set.
:accept_html:       True if ``text/html`` mime type is in ``Accept`` header.
:accept_xhtml:      True if ``text/xhtml`` mime type is in ``Accept`` header.
:accept_json:       True if ``application/json`` mime type is in ``Accept``
                    header.
:is_xhr:            True if ``X-Requested-With`` is ``XMLHttpRequest``.
:cookies:           Cookie object created from ``Cookie`` header or empty tuple.
:authorization:     Parsed ``Authorization`` header as a dictionary.
:referer:           HTTP referer from ``Referer`` header or None.
:user_agent:        User's client from ``User-Agent`` header or None.
:forwarded_for:     Value of ``X-Forward-For`` header or None.
:forwarded_host:    Value of ``X-Forward-Host`` header or None.
:forwarded_proto:   Value of ``X-Forward-Proto`` header or None.

Response Headers
~~~~~~~~~~~~~~~~
Response headers use the same Headers class as in the request object.
If you don't set a header when you create a Response object,
the default ``X-Powered-By`` header is set to "Poor WSGI for Python". The
``Content-Type`` and ``Content-Length`` headers are appended automatically. Each
header key must appear at most once, except for ``Set-Cookie``, which can be set
multiple times.

.. code:: python

    @app.route('/some/path')
    def some_path(req):
        xparam = int(req.headers.get('X-Param', '0'))
        # res.headers will have X-Powered-By, Content-Type and Content-Length
        res = Response("O yea!", content_type="text/plain")
        # res.headers["S-Param"] = "00" by default
        res.add_header("S-Param", xparam*2)
        return res

Sessions
~~~~~~~~
PoorWSGI provides a ``Session`` base class and ``PoorSession`` which extends
it. Both share the same interface.

Session
```````
``Session`` is a thin wrapper around ``http.cookies.SimpleCookie``. It is
suitable when the cookie value is either a **server-side session ID** (the
server holds the real data) or a **JWT** (which provides its own signature).
No encryption is applied — the value is stored as-is in the cookie.

.. code:: python

    from poorwsgi.session import Session

    # Store a session-id issued by the server
    session = Session(sid="SESSID", secure=True, same_site="Lax")
    session.data = generate_session_id()   # any string value
    session.write()
    session.header(response)

    # Read back
    session = Session()
    session.load(req.cookies)
    server_data = server_store[session.data]

The ``Session`` class accepts the following keyword arguments:
``sid``, ``expires``, ``max_age``, ``domain``, ``path``, ``secure``,
``same_site``. It exposes ``load()``, ``write()``, ``destroy()``, and
``header()`` methods.

.. note::

    ``Session`` does **not** encrypt or sign the cookie value. If you store a
    predictable token, an attacker can forge it. Use a cryptographically random
    session ID or a properly signed JWT as the value.

PoorSession
```````````
``PoorSession`` extends ``Session`` and stores data as an **encrypted and
authenticated** dictionary directly in the cookie. PoorSession needs a
``secret_key``, which can be set via the ``poor_SecretKey`` environment
variable or the ``Application.secret_key`` property.

**Security model** (XOR + substitution variant, no external dependencies):

* **Integrity** — The cookie is signed with HMAC-SHA256. Any modification
  by the client is detected and the cookie is rejected. An attacker cannot
  forge a valid cookie without knowing the secret key.

* **Confidentiality** — The data are protected by a XOR stream cipher with a
  1024-byte keystream (derived via ``shake_256``) combined with a
  byte-substitution step. This is a custom construction, **not AES**.
  A passive attacker who can collect a large number of cookies from different
  users (roughly 512 or more) may be able to reconstruct the keystream via
  a known-plaintext attack (JSON data always starts with ``{"``), and
  subsequently read the contents of other cookies. **Do not store highly
  sensitive data** (passwords, private keys, …) in the cookie. Store only
  session identifiers, user IDs, or non-critical flags.

* **Upgrade notice** — Updating PoorWSGI to a version that changes the
  encryption scheme (e.g. changes ``KEYSTREAM_SIZE``, switches from SHA-3
  to shake, or adds HMAC) will **invalidate all existing cookies**. Users
  will be logged out after a server restart / upgrade. This is expected
  behaviour.

* **Cookie format**: ``base64(ciphertext).base64(hmac-sha256)``

The ``KEYSTREAM_SIZE`` constant in ``poorwsgi.session`` controls the keystream
length (default ``1024``). Increasing it makes known-plaintext attacks harder
at the cost of slightly larger memory usage per session instance. Changing it
invalidates all existing cookies.

.. code:: python

    from functools import wraps
    from os import urandom

    import logging as log

    from poorwsgi import Application, state, redirect
    from poorwsgi.session import PoorSession


    app = Application('test')
    app.secret_key = urandom(32)                    # random secret_key

    def check_login(fn):
        @wraps(fn)      # using wraps make right/better /debug-info page
        def handler(req):
            cookie = PoorSession(app.secret_key)
            cookie.load(req.cookies)
            if "passwd" not in cookie.data:         # expires or didn't set
                log.info("Login cookie not found.")
                redirect("/login", message=b"Login required")
            return fn(req)
        return handler

    @app.route('/login', method=state.METHOD_GET_POST)
    def login(req):
        if req.method == 'POST':
            passwd = req.form.getfirst('passwd', func=str)
            if passwd != 'SecretPasswds':
                log.info('Bad password')
                redirect('/login', text='Bad password')

            response = RedirectResponse("/private/path")
            cookie = PoorSession(app.secret_key)
            cookie.data['passwd'] = passwd
            cookie.header(response)
            abort(response)

        return 'some html login form'


    @app.route('/private/path')
    @check_login
    def private_path(req):
        return 'Some private data'


    @app.route('/logout')
    def logout(req):
        response = RedirectResponse("/login")
        cookie = PoorSession(app.secret_key)
        cookie.destroy()
        cookie.header(response)
        return response

AES Session
```````````
``AESSession`` is a stronger alternative to ``PoorSession`` that uses
AES-256-CTR for confidentiality and HMAC-SHA256 for integrity.  It inherits
from ``Session`` and lives in a separate module because it requires the
``pyaes`` package:

.. code:: sh

    pip install pyaes

Usage is identical to ``PoorSession``:

.. code:: python

    from poorwsgi.aes_session import AESSession

    app.secret_key = urandom(32)

    cookie = AESSession(app.secret_key)
    cookie.data['user'] = username
    cookie.header(response)

The cookie format is ``base64(nonce + ciphertext).base64(hmac-sha256)``.
A 16-byte random nonce is generated on every ``write()`` call to prevent
CTR nonce reuse.  A missing or tampered signature causes ``SessionError``
to be raised in ``load()``.

JSON Web Tokens
```````````````



HTTP Digest Auth
~~~~~~~~~~~~~~~~

PoorWSGI supports HTTP Digest Authorization from version 2.3.x. Supported features
are:

    * MD5, MD5-sess, SHA-256, SHA-256-sess algorithm, **MD5-sess** is default
    * none or auth quality of protection (qop), **auth** is default
    * nonce value timeout, so new hash will be count every N seconds,
      **300** sec (5min) is default
    * The ``nc`` header value from the browser **is not currently checked** on the
      server side.


Application settings
````````````````````

There are some application options that are used for HTTP Authorization
configuration.

    :secret_key:        Secret Key is used for generating ``nonce`` value,
                        which is server side token.
    :auth_type:         At this moment, only ``Digest`` value can be set.
    :auth_algorithm:    You can choose algorithm type for hash computing. But
                        most browser understand only ``MD5`` or ``MD5-sess``,
                        which is default. ``SHA256`` is supported by PoorWSGI
                        too.
    :auth_qop:          Only ``auth`` is supported. You can switch off it, when
                        you set it to ``None`` or empty string.
    :auth_timeout:      You can set timeout for ``nonce`` token, so browser must
                        generate new hash values at least each *timeout* value.
    :auth_map:          Must be dictionary of dictionary of users digests. You
                        can use PasswordMap, which has some additional methods
                        for managing it, and save to / load from standard
                        digest files.

.. code:: python

    from poorwsgi import Application

    app = Application(__name__)
    # secret key must set before auth_type
    app.secret_key = sha256(str(time()).encode()).hexdigest()
    app.auth_type = 'Digest'
    app.auth_map = PasswordMap('test.digest')
    app.auth_map.load()  # load table from test.digest file

Usage
`````

There is a check_digest decorator, which can be used to check the
``Authorization`` header in client requests. Be careful when overriding the
default HTTP_UNAUTHORIZED handler - it must return the correct
``WWW-Authenticate`` header when the browser does not send a valid
``Authorization`` header.

.. code:: python

    @app.route('/admin_zone')
    @check_digest('Admin Zone')
    def admin_zone(req):
        """Page only for *Admin Zone* realm."""
        return "You are %s user" % req.user.


    @app.route('/user')
    @check_digest('User Zone', 'foo')
    def user_only(req):
        """Page only for *foo* user in *User Zone* only."""
        ...

The poorwsgi.digest module can also be used for managing the digest file. You
can also manage PasswordMap directly with its methods.

.. code:: sh

    python3 -m poorwsgi.digest -c digest.passwd 'User Zone' bfu
    ...

    # see full help
    python3 -m poorwsgi.digest -h


Debugging
---------
Poor WSGI has a few debugging mechanisms you can use. First, it is a
good idea to set the poor_Debug variable. If this variable is set, there is a
full traceback on the internal_server_error page (HTTP 500).

The second effect of this variable is enabling the special debug page at
``/debug-info`` URL. On this page, you can find:

    * a full handlers table with request paths, HTTP methods, and handlers that
      are called to serve those requests.
    * an HTTP state handlers table with HTTP status codes, HTTP methods, and
      handlers that are called when those HTTP states are raised.
    * the request headers sent by your browser when you access the debug page.
    * the Poor WSGI configuration variables for the current application instance.
    * application variables, which are set like connector variables but with
      the app\_ prefix.
    * the request environment, which is passed from the WSGI server to the WSGI
      application, that is, to the Poor WSGI connector.

Profiling
~~~~~~~~~
If you want to profile your request code, you can do so with a profiler. The Poor
WSGI application object has methods to set up profiling. You only need to provide
a runctx function, which is called before every request. For each request, a
.profile dump file will be generated for analysis.

If you want to profile the entire process from the start of your application,
you can create a file that profiles the import of your application, which in
turn imports the Poor WSGI connector.

.. code:: python

    import cProfile

    # this import your application, which import Poor WSGI, so you can profile
    # first server init, which is do, when server import your application.
    # don't forget to import this file instead of simple.py or your
    # application file
    cProfile.runctx('from simple import *', globals(), locals(),
                    filename="log/init.profile")

    # and this sets profiling of any request which is server by your
    # web application
    app.set_profile(cProfile.runctx, 'log/req')

When you use this file instead of your application file (simple.py for
example), the application creates files in the log directory. The first file will
be init.profile, created from the initial import by the WSGI server. Other files
will look like req\_.profile, req_debug-info.profile, etc. The second parameter of
the set_profile method is the prefix for output file names. File names are created
from the URL path, so each URL creates its own file.

There is a useful tool to view these profile files called runsnakerun. You can
download it from http://www.vrplumber.com/programming/runsnakerun/. Using it is
very simple - just open a profile file:

.. code:: sh

    $~ python runsnake.py log/init.profile
    $~ python runsnake.py log/req_.profile


OpenAPI
-------
OpenAPI aka Swagger 3.0 is a specification for RESTful API documentation and
request and response validation. PoorWSGI has an
`openapi_core <https://github.com/p1c2u/openapi-core>`_ wrapper in the
``openapi_wrapper`` module. You only need to declare your before and after
response handlers.

This wrapper is the only place where the **openapi_core** Python package is
used, so it is not in PoorWSGI's requirements. You need to install it separately:

.. code:: sh

    $~ pip install openapi_core

Example code of usage:

.. code:: python

    from os import path

    import json
    import logging

    from openapi_core import create_spec
    from openapi_core.validation.request.validators import RequestValidator
    from openapi_core.validation.response.validators import ResponseValidator
    from openapi_core.schema.operations.exceptions import InvalidOperation
    from openapi_core.schema.servers.exceptions import InvalidServer
    from openapi_core.schema.paths.exceptions import InvalidPath

    from poorwsgi import Application
    from poorwsgi.response import Response, abort
    from poorwsgi.openapi_wrapper import OpenAPIRequest, OpenAPIResponse

    app = Application("OpenAPI3 Test App")

    request_validator = None
    response_validator = None


    with open(path.join(path.dirname(__file__), "openapi.json"), "r") as openapi:
        spec = create_spec(json.load(openapi))
        request_validator = RequestValidator(spec)
        response_validator = ResponseValidator(spec)


    @app.before_response()
    def before_each_response(req):
        req.api = OpenAPIRequest(req)
        result = request_validator.validate(req.api)
        if result.errors:
            errors = []
            for error in result.errors:
                if isinstance(error, (InvalidOperation, InvalidServer,
                                      InvalidPath)):
                    logging.debug(error)
                    return  # not found
                errors.append(repr(error)+":"+str(error))
            abort(Response(json.dumps({"error": ';'.join(errors)}),
                           status_code=400,
                           content_type="application/json"))


    @app.after_response()
    def after_each_response(req, res):
        """Check answer by OpenAPI specification."""
        result = response_validator.validate(
            req.api or OpenAPIRequest(req),
            OpenAPIResponse(res))
        for error in result.errors:
            if isinstance(error, InvalidOperation):
                continue
            logging.error("API output error: %s", str(error))
        return res

Of course, you need ``openapi.json`` file with OpenAPI specification, where you
specified your API.
