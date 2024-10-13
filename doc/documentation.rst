Responses
---------
The main goal of all WSGI middleware is return response corresponding to HTTP,
resp. WSGI request. Responding in PoorWSGI is just like other knows frameworks.

Returning values
~~~~~~~~~~~~~~~~

Just value
``````````
The easiest way is return string or bytes. String values are automatically
convert to bytes, because it's WSGI internal. HTTP Response is 200 OK with
``text/html; character=utf-8"`` content type and default X-Powered-By header.

.. code:: python

   @app.route('/some/path')
   def some_path(req):
      return 'This is content for some path'

This examples returns the same values.

.. code:: python

   @app.route('/other/path')
   def some_path(req):
      return b'This is content for some path'

Generator
`````````
Second way is return generator. You can return any iterable object, but it must
be always as first parameter, resp. that can't be tuple!
*See Returned parameters*. Generator must always return bytes!

.. code:: python

    @app.route('/list/of/bytes')
    def list_of_bytes(req):
        return [b'Hello ',
                b'world!']

Or you can return any function which is generator.

.. code:: python

    @app.route('/generator/of/bytes')
    def generator_of_bytes(req):
        def generator():
            for i in range(10):
                yield b'%d -> %x\n' % (i, i)
        return generator()

Or the handler could be generator.

.. code:: python

    @app.route('/generator/of/bytes')
    def generator_of_bytes(req):
        for i in range(10):
            yield b'%d -> %x\n' % (i, i)

Returned parameters
```````````````````
In fact, you can return more then one value. You can returned content type,
headers and status code next parameters. Python return all parameters as one
tuple. That is not need to append brackets around them.

.. code:: python

    @app.route('/text/message')
    def text_message(req):
        return "Hello world!", "text/plain"

The first argument can be still generator.

.. code:: python

    @app.route('/generator/of/bytes')
    def generator_of_bytes(req):
        def generator():
            for i in range(10):
                yield b'%d -> %x\n' % (i, i)
        return generator(), "text/plain", ()    # empty headers

All values could looks like:

.. code:: python

    @app.route('/hello')
    def hello(req):
        return "Hello world!", "text/plain", ('X-Attribute', 'hello world'),
               HTTP_OK

Returning Responses
~~~~~~~~~~~~~~~~~~~

make response
`````````````
Response are the base class fore returning values. In fact, from other values
which are returned from request handlers are converted to Response object, via
make_response function.

.. code:: python

    def make_response(data, content_type="text/html; character=utf-8",
                      headers=None, status_code=HTTP_OK)


data : str, bytes, dict, list, None or generator
    Returned value as response body. Each type of data returns different
    response type:

        - str, bytes - Response
        - dict, list - JSONResponse
        - None - NoContentReponse
        - generator - GeneratorResponse

content_type : str
    The ``Content-Type`` header which is set, if this header is not set
    in headers.
headers : Headers, tuple, dict, ...
    If is Headers instance, that be set *(referer)*. Other types, are send
    to Headers constructor.
status_code : int
    HTTP status code, HTTP_OK is 200.

You can use headers instead of `content_type` argument.

.. code:: python

    @app.http_state(NOT_FOUND)
    def not_found(req, *_):
        return make_response(b'Page not Found',
                             headers={"Content-Type": "text/plain"},
                             status_code=NOT_FOUND)

If you return just simple type, or tuple of arguments, PoorWSGI automatically
call make_response function to create response for you.

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
Response object is one of base element of WSGI application. Response is object
which have full data, to return valid HTTP answer to client. Status code,
text reason of status code, headers and body. That's all. All values returned
from handlers is transform to Response object if it is possible. If handlers
return valid Response it will be returns.

Response have some functionality, to be useful like write method, to appending
to body with auto-counting ``Content-Length``, or some headers additional work.

.. code:: python

    @app.route('/teapot')
    def teapot(req):
        return Response("I'm teapot :-)", content_type="text/plain",
                        status_code=418)

There are some additional subclasses with special working.

JSONResponse
````````````
There is JSONResponse class to fast way for returning JSON.

.. code:: python

    @app.route('/json')
    def teapot(req):
        return JSONReponse(status_code=418, message="I'm teapot :-)",
                           numbers=list(range(5)))

This response returned these data with status code 418:

.. code:: json

    {
        "message": "I\'m teapot :-)",
        "numbers": [0, 1, 2, 3, 4]
    }

Or you can simple return dictionary or list. It will be automatically convert
to JSONResponse by make_response function. So it is similar to return text or
bytes.

Be careful that your dict or list **have to be convertible** to JSON by
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
There is JSONGeneratorResponse class too, which could return JSON, but
it could accept generators as arrays. And of course, this response
is returned by stream like GeneratorResponse, so data is not buffered
in memmory if wsgi server don't do that.

.. code:: python

    @app.route('/json-generator')
    def teapot(req):
        return JSONGeneratorReponse(status_code=418, message="I'm teapot :-)",
                                    numbers=range(5))

This response returned these data with status code 418:

.. code:: json

    {
        "message": "I\'m teapot :-)",
        "numbers": [0, 1, 2, 3, 4]
    }

FileResponse
````````````
File response open the file and send it throw ``wsgi.filewrapper``, which could
be *sendfile()* call. See PEP 3333. Content type and length read from system.

.. code:: python

    @app.route('/favicon.ico')
    def favicon(req):
        return FileResponse("/favicon.ico")

GeneratorResponse
`````````````````
Response which is use for generator values. Generator **must** return bytes,
instead of strings! For string returned generator, use **StrGeneratorResponse**,
which use generator for utf-8 encoding to bytes.

NoContentResponse
`````````````````
Sometimes you don't want to response payload. NoContentResponse has default code
`204 No Content`.

RedirectResponse
````````````````
Response with interface for more comfortable redirect response.

.. code:: python

    @app.route("/old/url")
    def old_url(req):
        return RedirectResponse("/new/url", True)

NotModifiedResponse
```````````````````
NotModifiedResponse is base on NoContentResponse with status code
`304 Bot Modified`. You have to add some Not Modified header in headers
parameters or as constructor argument.

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
Sometimes, you want to return partial Content, which is typical reaction to
`Range` headers. For that situations, there are `parse_range` function and
`make_partial` Response method.

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
For special use cases, programmer have own mechanism to select range, for example, if units is not bytes. For that situations, there is PartialResponse, which is similar to Response, but it is ``206 Partial Content`` yet, and you have to use ``make_range`` method to only create right ``Content-Range`` header.

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
There is HTTPException class, based from Exception, which is used for stopping
handler with right http status. There is possible two scenarios.

You want to stop with specific HTTP status code, and handler from application
was used to generate right response.

.. code:: python

    @app.route("/some/url")
    def some_url(req):
        if req.is_xhr:
            raise HTTPException(HTTP_BAD_REQUEST)
        return "Some message", "text/plain"

Or you would stop with specific response. Instead of status code, just use
Response object.

.. code:: python

    @app.route("/other/url")
    def some_url(req):
        if req.is_xhr:
            error = Response(b'{"reason": "Ajax not suported"}',
                             content_type="application/json",
                             status_code=HTTP_BAD_REQUEST)
            raise HTTPException(error)
        return "Other message", "text/plain"

**Additional functionality)**

If status code is ``DECLINED``, that return nothing. That means, that no status
code, no headers, no response body. Just stop the request.

If status code is ``HTTP_NO_CONTENT``, that return NoContentResponse, so message
body is not send.

When the handler raise any other exception, that generate Internal Server Error
status code.

Compatibility
`````````````
For compatibility with old PoorWSGI and other WSGI middleware, there are two
functions.

**redirect**

Have the same interface as RedirectResponse, and only raise the HTTPException
with RedirectResponse.

**abort**

Have the same interface as HTTPException, and voila, it raise the HTTPException.

Routing
-------

There are two ways how to set path handler. Via decorators of Application object,
or method set\_ where one of parameter is your handler. It is important how look
your application. If your web project have one or a few files where your
handlers are, it is good idea to use decorators. But if you have big project
with more files, it could be difficult to load all files with decorated
handlers. So that is right job for set\_ methods in one file, like a route file
or dispatch table.

Static Routing
~~~~~~~~~~~~~~
There are method and decorator to set your function (handler) to response static
route. Application.set_route and Application.route. Both of them have tho
parametrs, first the required path like ``/some/path/for/you`` and next method
flags, which is default METHOD_HEAD | METHOD_GET. There are other methods
in state module like METHOD_POST, METHOD_PUT etc. There is two special constants
METHOD_GET_POST which is HEAD | GET | POST, aned METHOD_ALL which is all
supported methods. If method does not match, but path is exist in internal
table, http state HTTP_METHOD_NOT_ALLOWED is return.

.. code:: python

    @app.route('/some/path')
    def some_path(req):
        return 'Data of some path'

    def other_path(req):
        return 'Data of other path'
    app.set_route('/some/other/path', other_path, state.METHOD_GET_POST)

You pop from application table via method Application.pop_route, or get internal
table via Application.routes property. **Each path can have only one handler**,
but one handler can be use for more path.

Regular expression routes
~~~~~~~~~~~~~~~~~~~~~~~~~
As in other wsgi connectors, or frameworks if you want, there are way how to
define routes with getting part of url path as parameter of handler. PoorWSGI
call them **regular expression routes**. You can use it in nice human-readable
form or in your own regular expressions. Basic use is define by group name.

.. code:: python

    # group regular expression
    @app.route('/user/<name>')
    def user_detail(req, name):
        return 'Name is %s' % name

There are use filters define by regular expression from table
Application.filters. This filter is use to transport to regular expression
define by group. Default filter is ``r'[^/]+'`` with str convert function. You
can use any filter from table filters.

.. code:: python

    # group regular expression with filter
    @app.route('/<surname:word>/<age:int>')
    def surnames_by_age(req, surname, age):
        return 'Surname is: %s and age is: %d' % (surname, age)

Filter int is define by ``r'-?\d+'`` with convert "function" int. So age must be
number and the input parameter is int instance.

There are predefined filters, for example: **:int**, **:word**, **:re:** and
**none** as default filter. Word is define as ``r'\w+'`` regular expression,
and poorwsgi use re.U flag, so it match any Unicode string. That means UTF-8
string. For all filters see Application.filters property or ``/debug-info`` page.

You can get copy of filters table calling Application.filters property. And this
filters table is output to debug-info page. Adding your own filter is possible
with function set_filter with name, regular expression and convert function
which is str by default. Next you can use this filter in group regular
expression.

.. code:: python

    app.set_filter('email', r'[a-zA-Z\.\-]+@[a-zA-Z\.\-]+', str)

    @app.route('/user/<login:email>')
    def user_by_login(req, login):
        return 'Users email is %s' % login

In other way, you can use filters define by inline regular expression. That is
``:re:`` filter. This filter have regular expression which you write in, and
allways str convert function, so parametr is allways string.

.. code:: python

    @app.route('/<number:re:[a-fA-F\d]+>')
    def hex_number(req, number):
        return ('Number is %s that is %d so %x' %
                (number, int(number,16), int(number,16)))

Group naming
~~~~~~~~~~~~
Group names **must be unique** in defined path. They are store in ordered
dictionary, to do wrap by their convert functions. You can named them in route
definition how you can, and they can't be named same in handler parameters,
but they must be only in the same ordering. Be careful to named parameters
in handler with some python keyword, like class for example. If you can, you can
use python "varargs" syntax to get any count of parameters in your handler
function.

.. code:: python

    @app.route('/test/<variable0>/<variable1>/<variable2>')
    def test_varargs(req, *args):
        return "Parse %d parameters %s" % (len(args), str(args))

At last future of regular expression routes is direct access to dictionary
with req.groups variable. This variable is set from any regular expression
route.

.. code:: python

    @app.route('/test/<variable0>/<variable1>/<variable2>')
    def test_varargs(req, *args):
        return "All input variables from url path: %s" % str(req.groups)

Regular expression routes as like static routes could be set with
Application.route or Application.set_route methods. But internaly
Application.regular_route or Application.set_regular_route is call.
Same situation is with Application.pop_route and Application.pop_regular_route.

Other handlers
--------------

Default handler
~~~~~~~~~~~~~~~
If no route is match, there are two ways which could occur. First is call
default handler if method match of course. Default handler is set with default
Application.decorator or Application.set_default method. Parameter is only
method which is default in METHOD_HEAD | METHOD_GET too. Instead of route
handlers, when method does not match, 404 error was returned.

So default handler is fallback with ``r'/.*'`` regular expression. For example,
you can use is for any OPTIONS method.

.. code:: python

    @app.default(METHOD_OPTIONS):
    def default(req):
        return b'', '', {'Allow': 'OPTIONS', 'GET', 'HEAD'}

Be careful, default handler is call before 404 not found handler. When it is
possible to serve request any other way, it will. For example if
poor_DocumentRoot is set and PoorWSGI found the file, that will be send.
Of course, internal file or dictionary handler is use only with METHOD_GET
or METHOD_HEAD.

HTTP state handlers
~~~~~~~~~~~~~~~~~~~
There are some predefined HTTP state handlers, which are use when other
HTTP state are raised via HTTPException or any other exception which ends with
HTTP_INTERNAL_SERVER_ERROR status code.

You can redefined your own handlers for any combination of status code and
method type like routes handlers. Response from these handlers are same as in
route handlers.

Be sure, that some http_state handlers can add other keyword arguments.

.. code:: python

    @app.http_state(state.HTTP_NOT_FOUND)
    def page_not_found(req, *_):
        return "Your request %s not found." % req.path, "text/plain"

If your http state (error) handler was crashed with error, internal server
error was return and right handler is called. If this your handler was crashed
too, default poor WSGI internal server error handler is called.

Error handlers
~~~~~~~~~~~~~~
In most cases, when exception was raised from your handler, *Internal Server
Error* was returned from server. When you want to handle each type of exception,
you can define your own error handler, which will be called instead of
HTTP_INTERNAL_SERVER_ERROR state handler.

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


Exception handlers are stored in OrderedDict, so exception type is checked in
same order as you set error handlers. So you must define handler for base
exception last.

Before and After response
~~~~~~~~~~~~~~~~~~~~~~~~~

PoorWSGI have too special list of handlers. First is iterate and call before
each response. You can add function with Application.before_response and
Application.after_response decorators or Application.add_before_response and
Application.add_after_response methods. And there are
Application.pop_before_response and Application.pop_after_response methods
to remove handlers.

Before response handlers are called in order how was added to list. They don't
return anything, resp. their return values are ignored. If they crash with
error, internal_server_error was return and http state handler was called.

After response handlers are called in order how was added to list. If they
crash with error, internal_server_error was return and http state handler is
called, but all code from before response list and from route handler was
called.

After response handler is call even if error handler, internal_server_error for
example was called.

Before response handler must have request argument, but after response handler
must have request and response argument.

.. code:: python

    @app.before_response()
    def before_each_response(request):
        ...

    @app.after_response()
    def after_each_response(request, response):
        ...


Filtering
`````````

TODO: How to write output filter, gzip for example....

WebSockets
~~~~~~~~~~

WebSockets are not directly supported in PoorWSGI, but upgrade requests can be
handled like other HTTP requests. See
`websocket.py <https://github.com/PoorHttp/PoorWSGI/blob/master/examples/websocket.py>`_
example which use uWsgi implementation or WSocket implementation.


Request variables
-----------------
PoorWSGI has two extra classes for get arguments. From request path, typical
for GET method and from request body, typical for POST method. This parsing is
enabled by default, but you can configure with options.

Query arguments
~~~~~~~~~~~~~~~
Request query arguments are stored to Args class, define in poorwsgi.request
module. Args is dict base class, with interface compatible methods getfirst
and getlist. You can access to variables with args parameters at all time when
poor_AutoArgs is set to On, which is default.

.. code:: python

    @app.route('/test/get')
    def test_get(req)
        name = req.args.getfirst('name')
        colors = req.args.getlist('color', func=int)
        return "Get arguments are %s" % str(req.args)

If no arguments are parsed, or if poor_AutoArgs is set to Off, req.args is
EmptyForm instance, which is dict base class too with both of methods.

Form arguments
~~~~~~~~~~~~~~
Request form arguments are stored in FieldStorage class, define in
poorwsgi.fieldstorage module. This class is inspired by FieldStorage from
legacy cgi module. Variables are parsed every time, when poor_AutoForm is set
to On, which is default, request method is POST, PUT or PATCH and request
mime type is one of `Application.form_mime_types`. You can call it
on any other methods of course, but it must exist wsgi.input in request
environment from wsgi server.

req.form instance is create with poor_KeepBlankValues and poor_StrictParsing
variables as Args class is create, but FieldStorageParser have file_callback
variable, which is configurable by Application.file_callback property.

.. code:: python

    @app.route('/test/post', methods = state.METHOD_GET_POST)
    def test_post(req)
        id = req.args.getfirst('id', 0, int) # id is get from request uri and it
                                             # is convert to number with zero
                                             # as default
        name = req.form.getfirst('name')
        colors = req.form.getlist('color', func=int)
        return "Post arguments for id are %s" % (id, str(req.args))

As like Args class, if poor_AutoForm is set to Off, or if method is no POST,
PUT or PATCH, req.form is EmptyForm instance instead of FieldStorage.

JSON request
~~~~~~~~~~~~
In the first place JSON request are from AJAX. There are automatic JSON
parsing in Request object, which parse request body to JSON variable. This
parsing starts only when Application.auto_json variable is set to True (default)
and if mime type of POST, PUT or PATCH request is application/json.
Then request body is parsed to json property. You can configure JSON types
via Application.json_mime_types property, which is list of request
mime types.

.. code:: python

    import json

    @app.route('/test/json',
               methods=state.METHOD_POST | state.METHOD_PUT | state.METHOD_PATCH)
    def test_json(req):
        for key, val in req.json.items():
            req.error_log('%s: %v' % (key, str(val)))

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

There are a few variants which req.json could be:

* JsonDict when dictionary is parsed.
* JsonList when list is parsed.
* Other based types from json.loads function like str, int, float, bool
  or None.
* None when parsing of JSON fails. That is logged with WARNING log level.

File uploading
~~~~~~~~~~~~~~
By default, FieldStorage store files somewhere to ``/tmp`` directory. This is
happened in FieldStorageParser, which calls ``TemporaryFile``. Uploaded files
are accessible like another form variables, but.

Any variables from FieldStorage is accessible with ``__getitem__`` method.
So you can get variable by ``req.form[key]``, which gets FieldStorage
instance. This instance has some attributes, which you can test,
what type of variable is it.

.. code:: python

    @app.route('/test/upload', methods = state.METHOD_GET_POST)
    def test_upload(req):
        # store file from upload variable to my_file_storage file
        if 'upload' in req.form and req.form['upload'].filename:
            with open('my_file_storage', 'w+b') as f:
                f.write(req.form['upload'].file.read())

Own file callback
~~~~~~~~~~~~~~~~~
Sometimes, you want to use your own file_callback, because you don't want to
use TemporaryFile as storage for this upload files. You can do it with simple
adding class, which is io.FileIO class in Python 3.x. Next only set
Application.file_callback property.

.. code:: python

    from poorwsgi import Application
    from io import FileIO

    app = Application('test')
    app.file_callback = FileIO

As you can see, this example works, but it is so bad solution of your problem.
Little bit better solution will be, if you store files only if exist and only
to special separate dictionary, which could be configurable. That you need use
to factory to create file_callback. In next example is written own form
processing, which is not important, when `file_callback` could be set via
Application property.

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

When HTTP Forms are base64 encoded, FieldStorageParser use readline on request
input file. This is not so optimal. So there is CachedInput class, which
is returned as wrapper around ``wsgi.input`` file.

Proccess variables
~~~~~~~~~~~~~~~~~~
Here is appliation variables, which is used to confiure request processing,
resp. which configure processing with request.


Application.auto_args
`````````````````````
If auto_args is set to ``True``, which is default, Request object parse input
arguments from request uri at initialisation. There will be ``Request.args``
property, which is instance of ``Args`` class. If you want to off this
functionality, set this property to ``False``. If argument parsing is disabled,
``Request.args`` will be instance of ``EmptyForm`` with same interface and no
data.

Application.auto_form
`````````````````````
If auto_form is set to ``True``, which is default, Request object parse input
arguments from request body at initialisation when request type is POST, PUT
or PATCH. There will be ``Request.form`` property which is instance of
``FieldStorage`` class. If you want to off this functionality, set this property
to ``False``. If form parsing is disabled, or JSON is detected, ``Request.form``
will be instance of ``EmptyForm`` with same interface and no data.

Application.form_mime_types
``````````````````````````````
List of mime types, which is parsed as input form by ``FieldStorageParser``
class. If input request does not have set one of these mime types, that form
will not be parsed.

Application.file_callback
`````````````````````````
Class or function, which is used to store file from form. See
`own file callback`_ for more details.

Application.auto_json
`````````````````````
If it is ``True``, which is default, method is POST, PUT or PATCH and request
mime type is json, than Request object do automatic parsing request body to
``Request.json`` dict property. If is disabled, or if form is detected, then
``EmptyForm`` instance is set.

Application.json_mime_types
``````````````````````````````
List of mime types, which is paresed as json by ``json.loads`` function.
If input request does not have set one of these mime types, that
``Request.json`` was not parsed.

Application.keep_blank_values
`````````````````````````````
This property is set for input parameters to automatically calling Args and
FieldStorageParser classes, when auto_args resp. auto_form is set. By default
this property is set to ``0``. If it set to ``1``, blank values should be
interpret as empty strings.

Application.strict_parsing
``````````````````````````
This property is set for input parameter to automatically calling Args and
FieldStorageParser classes. When auto_args resp. auto_form is set. By default
this variable is set to ``0``. If is set to ``1``, ValueError exception
could raise on parsing error. I'm sure, that you never want to set this
variable to ``1``. If so, use it in your own parsing.

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
When auto_cookies is set to ``True``, which is default, ``Request.cookies``
property is set when request heades contains ``Cookie`` header. Otherwise
empty tupple will be set.


Application / User options
--------------------------
Like in mod_python Request, Poor WSGI Application have get_options method too.
This method return dictionary of application options or variables, which start
with ``app_`` prefix. This prefix is cut from options names.

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

Output of application url /options looks like:

::

    db_file = mywebapp.db
    tmp_path = tmp
    templ = templ

You can store your variables to request object too. There are few reserved
variables for you, which poorwsgi never use, and which are None by default:

:req.user:   For user object, who is login, check_digest decorator set this
             variable.
:req.api:    For API checking. OpenAPIRequest use this variable.
:req.db:     For single database conection per request. You can store structure
             with more databases if you need to this vairable.
:req.app\_:  As prefix for any your application variable.

So if you want to add any other variable, be careful to named it.

Headers and Sessions
--------------------
Request Headers
~~~~~~~~~~~~~~~
We talk about headers in a few paragraph before. Now is time to more
information about that. Request object have headers_in attribute, which is
instance of wshiref.headers.Headers. This headers contains request headers
from client like in mod_python. You can read it as you can.

Next to it there are some Request properties, to get parset header values.

:headers:           Full headers object.
:mime_type:         Return mime type part from ``Content-Type`` header
:charset:           Return charset part from ``Content-Type`` header
:content_length:    Return content length if ``Content-Length`` header is set,
                    or -1 if not.
:accept:            List of ``Accept`` content neogetions set.
:accept_charset:    List of ``Accept-Charset`` content neogetions set.
:accept_encoding:   List of ``Accept-Encoding`` content neogetions set.
:accept_language:   List of ``Accept-Language`` content neogetions set.
:accept_html:       True if ``text/html`` mime type is in ``Accept`` header.
:accept_xhtml:      True if ``text/xhtml`` mime type is in ``Accept`` header.
:accept_json:       True if ``application/json`` mime type is in ``Accept``
                    header.
:is_xhr:            True if ``X-Requested-With`` is ``XMLHttpRequest``.
:cookies:           Cooike object created from ``Cookie`` header or empty tuple.
:authorization:     Parsed ``Authorization`` header to dictionary.
:referer:           Http referer from ``Referer`` header or None
:user_agent:        User's client from ``User-Agent`` header or None.
:forwarded_for:     Value of ``X-Forward-For`` header or None.
:forwarded_host:    Value of ``X-Forward-Host`` header or None.
:forwarded_proto:   Value of ``X-Forward-Proto`` header or None.

Response Headers
~~~~~~~~~~~~~~~~
Response headers is the same Request.Headers class as in request object. But
you can create it. If you don't set header when you create Response object,
default ``X-Powered-By`` header is set to "Poor WSGI for Python". The
``Content-Type`` and ``Content-Length`` headers are append automatically.
All headers keys must be set once, except of ``Set-Cookie``, which could be set
more times.

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
Like in mod_python, PoorSession is session class of PoorWSGI. It's
self-contained cookie which has data dictionary. Data are sent to client in
hidden, bzip2, base64 encoded format. PoorSession needs ``secret_key``,
which can be set by ``poor_SecretKey`` environment variable to
Application.secret_key property.

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
            cookie.load()
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

HTTP Digest Auth
~~~~~~~~~~~~~~~~

PoorWSGI supports HTTP Digest Authorization from version 2.3.x.
Supported are:

    * MD5, MD5-sess, SHA-256, SHA-256-sess algorithm, **MD5-sess** is default
    * none or auth quality of protection (qop), **auth** is default
    * nonce value timeout, so new hash will be count every N seconds,
      **300** sec (5min) is default
    * ``nc`` header value from browser **is not checked** on server side now


Application settings
````````````````````

There are some application options, which are used for HTTP Authorization
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

There is check_digest decorator, which can be used simply to check
``Authorization`` header in client requests. Be careful to overriding default
HTTP_UNAUTHORIZED handler, which must return right ``WWW-Authenticate`` header,
when browser doesn't sent right ``Authorization`` header.

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

The poorwsgi.digest module can be use for managing digest file too. But you
can manage PasswordMap directly with methods.

.. code:: sh

    python3 -m poorwsgi.digest -c digest.passwd 'User Zone' bfu
    ...

    # see full help
    python3 -m poorwsgi.digest -h


Debugging
---------
Poor WSGI have few debugging mechanism which you can to use. First, it could
be good idea to set up poor_Debug variable. If this variable is set, there are
full traceback on error page internal_server_error with http code 500.

Second effect of this variable is enabling special debug page on
``/debug-info`` url. On this page, you can found:

    * full handlers table with requests, http methods and handlers which are
      call to serve this requests.
    * http state handlers table with http state codes, http methods and handlers
      which are call when this http state is returned.
    * request headers table from your browser when you call this debug request
    * poor request variables, which are setting of actual instance of Poor WSGI
      configuration variables.
    * application variables which are set like a connector variables but with
      app\_ prefix.
    * request environment, which is set from your wsgi server to wsgi
      application, so to Poor WSGI connector.

Profiling
~~~~~~~~~
If you want to profile your request code, you can do with profiler. Poor WSGI
application object have methods to set profiling. You must only prepare runctx
function, which is call before all your request. From each your request will
be generate .profile dump file, which you can study.

If you want to profile all process after start your application, you can make
file, which profile importing your application, which import Poor WSGI
connector.

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

When you use this file instead of your application file, simple.py for
example, application create files in log directory. First file will be
init.profile from first import by WSGI server. Other files will look like
req\_.profile, req_debug-info.profile etc. Second parameter of set_profile
method is prefix of output file names. File name are create from url path, so
each url create file.

There is nice tool to view this profile files runsnakerun. You can download it
from http://www.vrplumber.com/programming/runsnakerun/. Using that is very
simple just open profile file:

.. code:: sh

    $~ python runsnake.py log/init.profile
    $~ python runsnake.py log/req_.profile


OpenAPI
-------
OpenAPI aka Swagger 3.0 is specification for RESTful api documentation and
request and response validation. PoorWSGI have
`openapi_core <https://github.com/p1c2u/openapi-core>`_ wrapper in
``openapi_wrapper`` module. You must only declare your before and after request
handler.

This wrapper is place where, **openapi_core** python package is use, so that is
not in PoorWSGI requirements. You need to install separately:

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
