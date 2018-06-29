Returning values
----------------
Any standard functions, resp. uri handlers got Request object as parameter,
and could end with a few of choices. First, known from another frameworks are
string. If string is returned, connector write that to internal buffer for
you, and set DONE value as finished state.

.. code:: python

   @app.route('/some/uri')
   def some_uri(req):
      return 'This is content for some uri'

Second, standard method of return content resp. end of uri handler is write
data to internal buffer and return some of state. This method is known from
apaches mod_python:

.. code:: python

    @app.route('/some/uri')
    def some_uri(req):
        req.write('This is content for some uri')
        return state.DONE

Last way, how uri handler could be ended, is raise SERVER_RETURN object,
which is known from apaches mod_python too. You can return as parametr of
SERVER_RETURN object one of request state: ``OK, DONE`` or ``DECLINED``
or in probably more times way, one of http state like as
``HTTP_MOVED_PERMANENTLY, HTTP_SEE_OTHER, HTTP_FORBIDDEN`` and so on.

.. code:: python

    @app.route('/some/uri')
    def some_uri(req):
        if not req.user:
            raise SERVER_RETURN(state.HTTP_FORBIDDEN)
        req.write('This is content for some uri')
        return state.DONE

PoorWSGI have try except blocks, where this SERVER_RETURN object is caught,
and if state is not one of ``OK, HTTP_OK`` or ``DONE``, HTTP state handler is
called.

As you can see, page data are returned as one big string, or could be write to
internal buffer. You can call flush method like in mod_pytho, which send data
at the moment of call of this method to WSGI server, but WSGI server can send
data to client at and of your handler.

Before you send data, it could be to set ``Content-Type`` header of page data.
Default vaule is ``text/html; charset=utf-8``. You change content type by
change Request.content_type variable or via Request.headers_out object.
``Content-Length`` was be set automatically if data are less then
poor_BufferSize. Or you can set content length via Request.content_lenght
property or Request.headers_out too.

.. code:: python

    @app.route('/some/uri')
    def some_uri(req)
        req.content_type = "text/plain; charset=utf-8"
        req.write('Some data')
        return state.DONE

There is one Request method, which write data to internal buffer, end WSGI
server of course for you: sendfile. Request.sendfile send file, or part of
file via internal call of Request.write method and return len of written data.

Routes and other handlers
-------------------------
There are too ways how to set handler. Via decorators of Application object, or
method set\_ where one of parameter is your handler. It is important how look
your application. If your web project have one or a few files where your
handlers are, it is good idea to use decorators. But if you have big project
with more files, it could be difficult to load all files with decorated
handlers. So that is right job for set\_ methods in one file, like a route file
or dispatch table.

Routes
~~~~~~
At this time, with this version, it could be set only simple routes with
decorator route or method set_route. Both of methods have too parameters, uri
and method, where uri is simple uri like ``/some/uri/for/you`` and method flags
which is default METHOD_HEAD | METHOD_GET. There are other methods in state
module like METHOD_POST, METHOD_PUT etc. There is two special constants
METHOD_GET_POST which is HEAD | GET | POST, aned METHOD_ALL which is all
supported methods. If method not match, but uri is exist in internal table,
http state HTTP_METHOD_NOT_ALLOWED is return.

.. code:: python

    @app.route('/some/uri')
    def some_uri(req):
        return 'Data of some uri'

    def other_uri(req):
        return 'Data of other uri'
    app.set_route('/some/other/uri', other_uri, state.METHOD_GET_POST)

Group regular expression routes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
As in other wsgi connectors, or frameworks if you want, there are way how to
define routes with getting part of url path as parameter of handler. I call
them **group regular expression routes**. You can use it in nice human-readable
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

Regular expression group naming
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Group names **must be unique**. They are store in ordered dictionary, to do wrap
by their convert functions. You can named them in route definition how you can,
and they can't be named same in handler parameters, but they must be only in the
same ordering. Be careful to named parameters in handler with some python
keyword, like class for example. If you can, you can use python "varargs" syntax
to get any count of parameters in your handler function.

.. code:: python

    @app.route('/test/<variable0>/<variable1>/<variable2>')
    def test_varargs(req, *args):
        return "Parse %d parameters %s" % (len(args), str(args))

At last future of group regular expression routes is direct access to dictionary
with req.groups variable. This variable is set from any regular expression
route.

.. code:: python

    @app.route('/test/<variable0>/<variable1>/<variable2>')
    def test_varargs(req, *args):
        return "All input variables from url path: %s" % str(req.groups)

Default and http state handler
------------------------------
If no route is match, there are two ways which could occur. First is call
default handler if method match of course. Default handler is set with default
decorator or set_default method. Parameter is only method which is default in
METHOD_HEAD | METHOD_GET too. Instead of route handlers, when method does not
match, 404 error was returned.

.. code:: python

    @app.default():
    def default(req):
        return 'this is default handler'

Of course, before calling default handler or 404 state handler, if is
poor_DocumentRoot set, poor WSGI try to find file which match uri path.

Second way how to handle 404 http state is handle http state. For this, there
are http_state decorator and set_http_state method. Like as route, functions
get code and method, but method is default in state ``METHOD_HEAD | METHOD_GET
| METHOD_POST``. You can handle all http states instead of ``HTTP_OK``. If you
do not handle some http state, Poor WSGI have its default handler, which is
``internal_server_error, forbidden, not_found, method_not_allowed`` and
``not_implemented``.

When you create your http state (error) pages, don't forget to set right
status, which is set like in mod_python with set status attribute of Request
object.

.. code:: python

    @app.http_state(state.HTTP_NOT_FOUND)
    def page_not_found(req):
        req.state = state.HTTP_NOT_FOUND
        req.write('Your request %s not found.' % req.uri)
        return state.DONE

If your http state (error) handler was crashed with error, internal server
error was return and right handler is called. If this your handler was crashed
too, default poor WSGI internal server error handler is called.

Pre and Post process functions
------------------------------
There are too special list of handlers. First is iter and call before each
request. You can add function with pre_process decorator or add_pre_process
method. Functions are called in order how is add to list. They don't return
anything, resp. their return values are ignored. If they crash with error,
internal_server_error was return and http state handler was called.

Second list contains functions, which is called after each request. If they
crash with error, internal_server_error was return and http state handler is
called, but all code from pre_process and from route handler is called, and
may be, it could send output to WSGI server, if content is bigger then
poor_BufferSize.

.. code:: python

    @app.pre_process()
    def before_each_request(req):
        ...

    @app.pre_process()
    def after_each_request(req):
        ...

You can use standard methods of app object, add_pre_process and
add_post_process too.

Request variables
-----------------
PoorWSGI has two extra classes for get arguments. From request uri, typical
for GET method and from request body, typical for POST method.ore details. If
this automatic parsing is disabled, a EmptyForm class is use.

**Application.auto_args**

If auto_args is set to ``True``, which is default, Request object parse input
arguments from request uri at initialisation. There will be ``args`` variable in
Request object, which is instance of ``Args`` class. If you want to off this
functionality, set this property to ``False``.

**Application.auto_form**

If auto_form is set to ``True``, which is default, Request object parse input
arguments from request body at initialisation when request type is POST, PUT
or PATCH. There will be ``form`` variable which is instance of FieldStorage
class. If you want to off this functionality, set this property to ``False``.

You must do it, if you want to set your own file_callback for
poorwsgi. FieldStorage.

**Application.auto_json**

If it is True (default), method is POST, PUT or PATCH and requset content type
is application/json, than Request object do automatic parsing request body to
json dict variable.

**Application.keep_blank_values**

This property is set for input parameters to automatically calling Args and
FieldStorage classes, when auto_args resp. auto_form is set. By default this
property is set to ``0``. If it set to ``1``, blank values should be interpret
as empty strings.

**Application.strict_parsing**

This property is set for input parameter to automatically calling Args and
FieldStorage classes. when auto_args resp. auto_form is set. By default this
variable is set to ``0``. If is set to ``1``, ValueError exception
could raise on parsing error. I'm sure, that you never want to set this
variable to ``1``. If so, use it in your own parsing.

.. code:: python

    app.auto_form = False
    app.auto_args = False
    app.strict_parsing = 1

    @app.pre_process()
    def auto_form_and_args(req):
        """ This is own implementation of req.form and req.args paring """

        try:
            req.args = request.Args(req,
                                    keep_blank_values=app.keep_blank_values,
                                    strict_parsing=app.strict_parsing)
        except Exception as e:
            req.log_error("Bad request uri: %s", e)

        if req.method_number == state.METHOD_POST:
            try:
                req.form = request.FieldStorage(
                    req,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing)
            except Exception as e:
                req.log_error("Bad request body: %s", e)

Automatic convert to string
~~~~~~~~~~~~~~~~~~~~~~~~~~~
As variables from uri, gets with group regular expression routes, which must
be string to right working regular expression. All other input variables
are string by default. You can call get method on each class with your convert
function of course.

Request uri arguments
~~~~~~~~~~~~~~~~~~~~~
Request uri arguments are stored to Args class, define in poorwsgi.request
module. Args is dict base class, with interface compatible methods getfirst
and getlist. You can access to variables with args parameters at all time when
poor_AutoArgs is set to On, which is default.

.. code:: python

    @app.route('/test/get')
    def test_get(req)
        name = req.args.getfirst('name')
        colors = req.args.getlist('color', fce=int)
        return "Get arguments are %s" % str(req.args)

If no arguments are parsed, or if poor_AutoArgs is set to Off, req.args is
EmptyForm instance, which is dict base class too with both of methods.

Request body arguments
~~~~~~~~~~~~~~~~~~~~~~
Request body areguments are stored to FieldStorage class, define in
poorwsgi.request module. This class is based on FieldStorage from standard
cgi module. And variables are parsed every time, when poor_AutoForm is set to
On, which is default and request method is POST, PUT or PATCH. You can call it
on any other methods of course, but it must exist wsgi.input in request
environment from wsgi server.

req.form instance is create with poor_KeepBlankValues and poor_StrictParsing
variables as Args class is create, but FieldStorage have file_callback
variable, which is configurable by XXX.

.. code:: python

    @app.route('/test/post', methods = state.METHOD_GET_POST)
    def test_post(req)
        id = req.args.getfirst('id', 0, int) # id is get from request uri and it
                                             # is convert to number with zero
                                             # as default
        name = req.form.getfirst('name')
        colors = req.form.getlist('color', fce=int)
        return "Post arguments for id are %s" % (id, str(req.args))

As like Args class, if poor_AutoForm is set to Off, or if method is no POST,
PUT or PATCH, req.form is EmptyForm is instance instead of FieldStorage.

JSON request
~~~~~~~~~~~~
In the first place JSON request are from AJAX. There are automatic JSON
parsing in Request object, which parse request body to JSON variable. This
parsing starts only when Application.auto_json variable is set to True (default)
and if content type of POST, PUT or PATCH request is application/json.
Then request body is parsed to json property.

.. code:: python

    import json

    @app.route('/test/json',
               methods=state.METHOD_POST | state.METHOD_PUT | state.METHOD_PATCH)
    def test_json(req):
        for key, val in req.json.items():
            req.error_log('%s: %v' % (key, str(val)))

        req.content_type = 'application/json'
        return json.dumps({'Status': '200', 'Message': 'Ok'})

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

File uploading
--------------
By default, pythons FieldStorage, so poorwsgi.FieldStorage too, store files
somewhere to /tmp dictionary. This works in FieldStorage, which calls
TemporaryFile. Uploaded files are accessible like another form variables, but.

Any variables from FieldStorage is accessible with __getitem__ method. So you
can get variable by {req.form[key]}, which gets FieldStorage instance. This
instance have some another variables, which you can test, what type of
variable is.

.. code:: python

    @app.route('/test/upload', methods = state.METHOD_GET_POST)
    def test_upload(req):
        # store file from upload variable to my_file_storage file
        if 'upload' in req.form and req.form['upload'].filename:
            with open('my_file_storage', 'w+b') as f:
                f.write(req.form['upload'].file.read())

Your own file callback
~~~~~~~~~~~~~~~~~~~~~~
Sometimes, you want to use your own file_callback, because you don't want to
use TemporaryFile as storage for this upload files. You can do it with simple
adding {file} class. But if you want to do in Python 3.x, you must add
io.FileIO class, cause file class not exist in Python 3.x.

.. code:: python

    from poorwsgi import Application, state, request
    from sys import version_info

    if version_info.major >= 3:
        from io import FileIO
        file = FileIO

    app = Application('test')

    # disable automatic request body parsing - IMPORTANT !
    app.auto_form = False

    @app.pre_process()
    def auto_form(req):
        if req.method_number == state.METHOD_POST:
            # store upload files permanently with their right file names
            req.form = request.FieldStorage(
                req,
                keep_blank_values=app.keep_blank_values,
                strict_parsing=app.strict_parsing,
                file_callback=file)

As you can see, this example works, but it is so bad solution of your problem.
Little bit better solution will be, if you store files only if exist and only
to special separate dictionary, which could be configurable. That you need use
factory to create file_callback.

.. code:: python

    from poorwsgi import Application, state, request
    from sys import version_info

    if version_info.major >= 3:
        from io import FileIO
        file = FileIO

    app = Application('test')

    class Storage(file):
        def __init__(self, directory, filename):
            self.path = directory + '/' + filename
            if os.access(self.path, os.F_OK):
                raise Exception("File %s exist yet" % filename)
            super(Storage, self).__init__(self.path, 'w+b')

    class StorageFactory:
        def __init__(self, directory):
            self.directory = directory
            if not os.access(directory, os.R_OK):
                os.mkdir(directory)

        def create(self, filename):
            return Storage(self.directory, filename)

    # disable automatic request body parsing - IMPORTANT !
    app.auto_form = False

    @app.pre_process()
    def auto_form(req):
        """ Own implementation of req.form paring before any POST request
            with own file_callback.
        """
        if req.method_number == state.METHOD_POST:
            factory = StorageFactory('./upload')
            try:
                req.form = request.FieldStorage(
                    req,
                    keep_blank_values=app.keep_blank_values,
                    strict_parsing=app.strict_parsing,
                    file_callback=factory.create)
            except Exception as e:
                req.log_error(e)

Application / User options
--------------------------
Like in mod_python Request, Poor WSGI Request have get_options method too.
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

    config = None

    @app.pre_process()
    def load_options(req):
        global config

        if config is None:
            config = req.get_options()

        req.config = config

    @app.route('/options')
    def list_options(req):
        for key, val in req.config.items():
            req.write(key + ' = '+ val)

Output of application url /options looks like:

::

    db_file = mywebapp.db
    tmp_path = tmp
    templ = templ

As you can see, you can store your variables to request object. There are few
reserved variables for you, which poorwsgi never use, and which are None by
default:

:req.config: for your config object
:req.logger: for your special logger object or logger function
:req.user:   for user object, who is login
:req.app\_:  as prefix for any your application variable

So if you want to add any other variable, be careful to named it.

.. code:: python

    from time import ctime

    log = open('app.log', 'w+')
    def my_logger(msg)
         log.write(ctime() + ': ' + msg + '\n')

    @app.pre_process()
    def set_logger(req):
        req.logger = my_logger

    @app.route('/test')
    def test(req):
        req.logger('test call')
        ...


Headers and Sessions
--------------------
Headers
~~~~~~~
We talk about headers in a few paragraph before. Now is time to more
information about that. Request object have headers_in attribute, which is
instance of wshiref.headers.Headers. This headers contains request headers
from client like in mod_python. You can read it as you can.

Next to it, there are two output attributes headers_out and err_headers_out.
Both of that are instance of Headers class from request module. The Headers
class is child of wsgiref.headers.Headers class with little additional. By
default there is ``X-Powered-By`` header set to "Poor WSGI for Python" and
add method raise exception if you try to set more same keys without
``Set-Cookie``.

Different before headers_out and err_headers_out is, that err_headers_out is
use in internal http state handlers like in mod_python.

.. code:: python

    @app.route('/some/uri')
    def some_uri(req):
        xparam = int(req.headers_in.get('X-Param', '0'))
        req.headers_out.add('My-Param', xparam * 2)
        ...

Sessions
~~~~~~~~
Like in mod_python, in poor WSGI is session class PoorSession. It is
self-contained cookie which have data dictionary. Data are sent to client in
hidden, bzip2ed, base64 encoded format. In read this session, expires value
are check from data, so client can't change it in simple way. That is
important to right set poor_SecretKey variable which is used in class by
hidden function.

.. code:: python

    from poorwsgi import Application, state, redirect
    from poorwsgi.session import PoorSession
    from os import urandom

    app = Application('test')
    app.secret_key = urandom(32)                    # random secret_key

    def check_login(fn):
        def handler(req):
            cookie = PoorSession(req)
            if 'passwd' not in cookie.data:         # expires or didn't set
                req.log_error('Login cookie not found.', state.LOG_INFO)
                redirect(req, '/login', text='Login required')
            return fn(req)
        return handler

    @app.route('/login', method = state.METHOD_GET_POST)
    def login(req):
        if req.method == 'POST':
            passwd = req.form.getfirst('passwd', fce=str)
            if passwd != 'SecretPasswds':
                req.log_error('Bad password', state.LOG_INFO)
                redirect(req, '/login', text='Bad password')

            cookie = PoorSession(req)
            cookie.data['passwd'] = passwd
            cookie.header(req, req.headers_out)
            redirect(req, '/private/uri')

        return 'some html login form'


    @app.route('/private/uri')
    @check_login
    def private_uri(req):
        return 'Some private data'


    @app.route('/logout')
    def logout(req):
        cookie = PoorSession(req)
        cookie.destroy()
        cookie.header(req, req.headers_out)
        redirect(req, '/login')


Debugging
---------
Poor WSGI have few debugging mechanism which you can to use. First, it could
be good idea to set up poor_Debug variable. If this variable is set, there are
full traceback on error page internal_server_error with http code 500.

Second property of this variable is enabling special debug page on
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
    # don'ŧ forget to import this file instead of simple.py or your
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

There is nice tool to view this profile files runsnakerun. You can download
from http://www.vrplumber.com/programming/runsnakerun/. Use that is very
simple just open profile file:

.. code:: sh

    $~ python runsnake.py log/init.profile
    $~ python runsnake.py log/req_.profile


