== Easy to use ==

Poor WSGI for Python is light WGI connector with uri routing between WSGI
server and your application. It have mod_python compatible request object,
which is post to all uri or http state handler. The simplest way to run and
test it looks like that:

    from wsgiref.simple_server import make_server
    from poorwsgi import *

    @app.route('/test')
    def root_uri(req):
        return 'Hello world'

    if __name__ == '__main__':
        httpd = make_server('127.0.0.1', 8080, app)
        httpd.serve_forever()

You can use python wsgiref.simple_server for test it:

    ~$ python simple.py

It has base error pages like 403, 404, 405, 500 or 501. When 500 internal server
error have debug output if poor_Debug is set. And there is special debug page
on /debug-info uri, which is available when poor_Debug is set too.

    ~$ poor_Debug=On python simple.py

Poor WSGI have some functions, to you can use as real http server, which could
send files with right mime-type from disk, or generate directory listing. See
Configuration section for more info.

    ~$ poor_Debug=On poor_DocumentRoot=./web poor_DocumentIndex=On python simple.py

If you are new with it, please see fast Tutorial on this page.

== Installation & Configuration ==
=== Install ===
==== Source tarbal ====


    #!text
    Not yet

==== Source from git ====


    #!text
    ~$ git clone git://git.code.sf.net/p/poorhttp/poorwsgi poorwsgi
    or
    ~$ git clone http://git.code.sf.net/p/poorhttp/poorwsgi poorwsgi

==== Install from PyPI ====


    #!text
    Not yet

=== Configuration ===
Poor WSGI is configured via environment variables with poor_* prefix.

==== poor_BufferSize ====
Buffer size in bytes is size of "FIFO" like buffer, which is used for every
request. Default value is 16384 bytes which is 16KiB.

==== poor_Debug ====
If poor_Debug is {On}, internal server error page have debug traceback and
{/debug-info} page is activate.

==== poor_DocumentIndex ====
If poor_DocumentRoot is set and poor_DocumentIndex is {On}, poor WSGI can
generate document index from dictionary like real http servers. Default is
{Off}.

==== poor_DocumentRoot ====
pooor_DocumentRoot is dictionary, which is accessible files from. Files are
sent via Request.sendfile method, which is not optimized yet. Method reads
data for poor_BufferSize size blocks. And of course, before files is set,
right {Content-Type} from mime-type and {Content-Length} headers are set.

==== poor_LogLevel ====
One of log level for error_log output like in Apache http server. All choices
are: {debug, info, notice, warn, error, alert, emerg}. Default is {warn} that
means warn, error, alert and emerg type of errors are send to error file from
WSGI, which is typical error_log file of WSGI server.

==== poor_SecretKey ====
If you want to use PoorSession class, as self-contained cookie, it is
*important* to set poor_SecretKey as pass phrase for hidden function, which is
call from PoorSession class. Default value is stupid string from versions and
server software which is really insufficient.

=== Poor HTTP server example ===
Poor WSGI variables are system environment variables, which could be set in
{environ} section in poorhttp.ini file. Only python file with {application}
function or class must be set in predefined variable in {http} section:

    #!ini
    [http]
    ...
    application = /srv/simple.py        # your main python file, where app, resp.
                                        # application from wsgi module is imported
    ...
    [environ]
    poor_Debug = Off                    # default
    poor_DocumentRoot = /srv/public
    poor_DocumentIndex = On
    poor_LogLevel = error               # only error alert an emerg type are log


=== uWsgi server example ===
uWsgi server have more choices how is configurable. Here is it's ini file,
which have one {uwsgi} section with {wsgi-file} variable, where we need to set
your main python file, and lots of env variables, which is use to set
environment variables.

    #!ini
    [uwsgi]
    ...
    wsgi-file = /srv/simple.py          # your main python file, where app, resp.
                                        # application from wsgi module is imported
    ...
    env = poor_Debug=On                 # variables must be set without space between
    env = poor_DocumentRoot=/srv/public # variable equation and value
    env = poor_SecretKey=MyApplication@Super!Secret?Password:-)

== Tutorial ==
=== Returning values ===
Any standard functions, resp. uri handlers got Request object as parameter,
and could end with a few of choices. First, known from another frameworks are
string. If string is returned, connector write that to internal buffer for
you, and set DONE value as finished state.

    @app.route('/some/uri')
    def some_uri(req):
        ...
        return 'This is content for some uri'

Second, standard method of return content resp. end of uri handler is write
data to internal buffer and return some of state. This method is known from
apaches mod_python:

    @app.route('/some/uri')
    def some_uri(req):
        ...
        req.write('This is content for some uri')
        return state.DONE

Last way, how uri handler could be ended, is raise SERVER_RETURN object, which
is known from apaches mod_python too. You can return as parametr of
SERVER_RETURN object one of request state: {OK, DONE or DECLINED}
or in probably more times way, one of http state like as
{HTTP_MOVED_PERMANENTLY, HTTP_SEE_OTHER, HTTP_FORBIDDEN} and so on.

    @app.route('/some/uri')
    def some_uri(req):
        ...
        if not user:
            raise SERVER_RETURN(state.HTTP_FORBIDDEN)
        req.write('This is content for some uri')
        return state.DONE

Poor WSGI have try except blocks, where this SERVER_RETURN object is caught,
and if state is not one of OK, HTTP_OK or DONE, http state handler is called.

As you can see, page data are returned as one big string, or could be write to
internal buffer. You can call flush method like in mod_pytho, which send data
at the moment of call of this method to WSGI server, but WSGI server can send
data to client at and of your handler.

Before you send data, it could be to set {Content-Type} header of page data.
Default vaule is '{text/html; charset=utf-8}'. You change content type by
change Request.content_type variable or via Request.headers_out object.
{Content-Length} was be set automatically if data are less then
poor_BufferSize. Or you can set content length via Request.set_content_lenght
method or headers_out too.

    @app.route('/some/uri')
    def some_uri(req)
        req.content_type = "text/plain; charset=utf-8"
        req.write('Some data')
        return state.DONE

There is one Request method, which write data to internal buffer, end WSGI
server of course for you: sendfile. Request.sendfile send file, or part of
file via internal call of Request.write method and return len of written data.

=== Routes and other handlers ===

There are too ways how to set handler. Via decorators of Application object, or
method set_ where one of parameter is your handler. It is important how look
your application. If your web project have one or a few files where your
handlers are, it is good idea to use decorators. But if you have big project
with more files, it could be difficult to load all files with decorated
handlers. So that is right job for set_ methods in one file, like a route file
or dispatch table.

==== Routes ====

At this time, with this version, it could be set only simple routes with
decorator route or method set_route. Both of methods have too parameters, uri
and method, where uri is simple uri like {/some/uri/for/you} and method flags
which is default METHOD_HEAD | METHOD_GET. There are other methods in state
module like METHOD_POST, METHOD_PUT etc. There is two special constants
METHOD_GET_POST which is HEAD | GET | POST, aned METHOD_ALL which is all
supported methods. If method not match, but uri is exist in internal table,
http state HTTP_METHOD_NOT_ALLOWED is return.

    @app.route('/some/uri')
    def some_uri(req):
        return 'Data of some uri'

    def other_uri(req):
        return 'Data of other uri'
    app.set_route('/some/other/uri', other_uri, state.METHOD_GET_POST)

==== rRoute and gRoute ====

As I wrote, at this time is support only simple routes. But regular
expression routes and group regular expressions routes are planned. There are
decorator app.rroute and app.groute and methods app.set_rroute and
app.set_groute which raise NotImplementedError exceptions.

=== Default and http state handler ===

If no route is match, there are two ways which could occur. First is call
default handler if method match of course. Default handler is set with default
decorator or set_default method. Parameter is only method which is default in
METHOD_HEAD | METHOD_GET too. Instead of route handlers, when method does not
match, 404 error was returned.

    @app.default():
    def default(req):
        return 'this is default handler'

Of course, before calling default handler or 404 state handler, if is
poor_DocumentRoot set, poor WSGI try to find file which match uri path.

Second way how to handle 404 http state is handle http state. For this, there
are http_state decorator and set_http_state method. Like as route, functions
get code and method, but method is default in state {METHOD_HEAD | METHOD_GET
| METHOD_POST}. You can handle all http states instead of HTTP_OK. If you do
not handle some http state, Poor WSGI have its default handler, which is
internal_server_error, forbidden, not_found, method_not_allowed and
not_implemented.

When you create your http state (error) pages, don't forget to set right
status, which is set like in mod_python with set status attribute of Request
object.

    @app.http_state(state.HTTP_NOT_FOUND)
    def page_not_found(req):
        req.state = state.HTTP_NOT_FOUND
        req.write('Your request %s not found.' % req.uri)
        return state.DONE

If your http state (error) handler was crashed with error, internal server
error was return and right handler is called. If this your handler was crashed
too, default poor WSGI internal server error handler is called.

==== Pre and Post process functions ====

There are too special list of handlers. First is iter and call before each
request. You can add function with pre_process decorator or add_pre_process
method. Functions are called in order how is add to list. They don'ŧ return
anything, resp. their return values are ignored. If they crash with error,
internal_server_error was return and http state handler was called.

Second list contains functions, which is called after each request. If they
crass with error, internal_server_error was return and http state handler is
called, but all code from pre_process and from route handler is called, and
may be, it could send output to WSGI server, if content is bigger then
poor_BufferSize.

=== Input Forms and Application options ===
==== Input variables / Forms ====

User input vairables, which is sent to server are available throw
FieldStorage class. FieldStorage is child of FieldStorage class from pythons
cgi module with some WSGI support init and additional functionality in
getfirst and getlist methods.

Both of methods have new parameter fce, This function is called on all
returned value and it is good idea to set it on your requested variable. If
you want to get number, you will every time got number if fce is int or float.

Before example, that not mind, if request method is get, post or another. You
can use FieldStorage every time.

    @app.route('/some/uri')
    def some_uri(req):
        form = FieldStorage(req)
        user = form.getfirst('name', '', str)       # because str(None) returns 'None'
        age  = form.getfirst('age', fce = int)      # there could raise exception
                                                    # because int(None) raise it
        children = form.getlist('children', '', str)
        ...

==== Application / User options ====
Like in mod_python Request, Poor WSGI Request have get_options method too.
This method return dictionary of application options or variables, which start
with {app_} prefix. This prefix is cut from options names.

    #!ini
    [uwsgi]                                         # uwsgi config example
    ...
    env = app_db_file = mywebapp.db                 # variable is db_file
    env = app_tmp_path = tmp                        # variable is tmp_path
    env = app_templ = templ                         # variable is templ

And you can get these variables with get_options method:

    @app.route('/options')
    def app_test(req):
        options = req.get_options()
        for key, val in options.items():
            req.write(key + '\t: '+ val)

Output of application url /options looks like:

    #!text
    db_file   : mywebapp.db
    tmp_path  : tmp
    templ     : templ

=== Headers and Sessions ===
==== Headers ====
We talk about headers in a few paragraph before. Now is time to more
information about that. Request object have headers_in attribute, which is
instance of wshiref.headers.Headers. This headers contains request headers
from client like in mod_python. You can read it as you can.

Next to it, there are two output attributes headers_out and err_headers_out.
Both of that are instance of Headers class from request module. The Headers
class is child of wsgiref.headers.Headers class with little additional. By
default there is {X-Powered-By} header set to "Poor WSGI for Python" and
add method raise exception if you try to set more same keys without
{Set-Cookie}.

Different before headers_out and err_headers_out is, that err_headers_out is
use in internal http state handlers like in mod_python.

    @app.route('/some/uri')
    def some_uri(req):
        xparam = int(req.headers_in.get('X-Param', '0'))
        req.headers_out.add('My-Param', xparam * 2)
        ...

==== Sessions ====

Like in mod_python, in poor WSGI is session class PoorSession. It is
self-contained cookie which have data dictionary. Data are sent to client in
hidden, bzip2ed, base64 encoded format. In read this session, expires value
are check from data, so client can't change it in simple way. That is
important to right set poor_SecretKey variable which is used in class by
hidden function.

    @app.route('/login')
    def login(req):
        if req.method == 'POST':
            passwd = form.getfirst('passwd', fce = str)
            if passwd != 'SecretPasswds':
                req.log_error('Bad password', state.LOG_INFO)
                redirect(req, '/login', text = 'Bad password')

            cookie = PoorSession(req)
            cookie.data['passwd'] = passwd
            cookie.header(req, req.headers_out)
            redirect(req, '/private/uri')

        return 'some html login form'


    @app.route('/private/uri')
    def private_uri(req):
        cookie = PoorSession(req)
        if not 'passwd' in cookie.data:         # expires or didn't set
            req.log_error('Login cookie not found.', LOG_INFO)
            redirect(req, '/login', text = 'Login required')

        return 'Some private data'


    @app.route('/logout')
    def logout(req):
        cookie = PoorSession(req)
        cookie.destroy()
        cookie.header(req, req.headers_out)
        redirect(req, '/login')


== Debugging ==
Poor WSGI have few debugging mechanism which you can to use. First, it could
be good idea to set up poor_Debug variable. If this variable is set, there are
full traceback on error page internal_server_error with http code 500.

Second property of this variable is enabling special debug page on /debug-info
url. On this page, you can found:
    * full handlers table with requests, http methods and handlers which are
      call to serve this requests.
    * http state handlers table with http state codes, http methods and handlers
      which are call when this http state is returned.
    * request headers table from your browser when you call this debug request
    * poor request variables, which are setting of actual instance of Poor WSGI
      configuration variables.
    * application variables which are set like a connector variables but with
      app_ prefix.
    * request environment, which is set from your wsgi server to wsgi
      application, so to Poor WSGI connector.

=== Profiling ===
If you want to profile your request code, you can do with profiler. Poor WSGI
application object have methods to set profiling. You must only prepare runctx
function, which is call before all your request. From each your request will
be generate .profile dump file, which you can study.

If you want to profile all process after start your application, you can make
file, which profile importing your application, which import Poor WSGI
connector.

    import cProfile

    # this import your application, which import Poor WSGI, so you can profile
    # first server init, which is do, when server import your application.
    # don'ŧ forget to import this file instead of simple.py or your
    # application file
    cProfile.runctx('from simple import *', globals(), locals(), filename="log/init.profile")

    # and this sets profiling of any request which is server by your
    # web application
    app.set_profile(cProfile.runctx, 'log/req')

When you use this file instead of your application file, simple.py for
example, application create files in log directory. First file will be
init.profile from first import by WSGI server. Other files will look like
req_.profile, req_debug-info.profile etc. Second parameter of set_profile
method is prefix of output file names. File name are create from url path, so
each url create file.

There is nice tool to view this profile files runsnakerun. You can download
from http://www.vrplumber.com/programming/runsnakerun/. Use that is very
simple just open profile file:

    #!text
    $~ python runsnake.py log/init.profile
    $~ python runsnake.py log/req_.profile


== Few word at the end ==
Once upon a time, there was a King. Ok there was a Prince. Oh, may by, there
was not a prince, but probably, there was a Programmer, hmm ok, programmer.
And this programmer know apaches mod_python. Yes it was very very bad paragon,
but before python, he was programing in php. So mod_python was be big movement
to right direction at that times.

He was founding how he can write, and host on server python applications. And as
he know some close-source framework, which works right, he write some another,
similar for his use. That is base of Poor Publisher. But WGSI was coming so he
had idea, to write some new backend for his applications. That is base of Poor
HTTP and Poor WSGI.

Some times, Poor HTTP and Poor WSGI was one project. It is better way, but
that's not right way. After some time, he divide these too projects to Poor WSGI
and Poor HTTP projects. But there is bad concept in Poor WSGI framework, which
is not framework in fact. So he look for another projects, and see how could be
nice to create WSGI application for user. That is time when Poor WSGI is
rewritten to library type code, and application is callable class with some nice
route and other methods - decorators.

This is story of one programmer and his WSGI framework, which is not framework
in fact, because, it knows only handle uri request with some mod_python
compatibility layer. As you can see, there are some ways, how this project can
go. It's author, programmer use it on his projects, and it would be so nice, if
there are more programmers then he, which use this little project, let's call
it WSGI connector.

If you have any questions, proposals, bug fixes, text corrections, or any
other things, please send me email to {*mcbig at zeropage.cz*} or send it to
discussion on SourceForge.Net:
https://sourceforge.net/p/poorhttp/discussion/poorwsgi/. Thank you so much.

=== ChangeLog ===
==== 0.9.1 rc ====
    * Profiler support for Application __call__ method
    * request_uri and some documentation update
    * do extensin in jinja24doc
    * up version of last bug fix
    * Request.referer variable
    * Bug fix
    * Documentation edit
    * Last part of main documentation
    * Part of documentation

==== 0.9 ====
    * redirect is possible when headers are fill, why not
    * Bug fix with raiseing errors
    * Document index bugfix
    * poorwsgi has it's own repository
    * some documentation fix
    * more then one pre and post handlers, some bugfixes ond documentations
    * Python package with setup.py
    * Import optimization
    * application is class instance now
    * Edit comment about PEP
    * Some bug fix and new Request member method_number
    * set functions for route, http_state and default, better pre-import
    * more methods support, better handlers working, lots of documentations
    * Library style
    * Some XXX comment - know bug
    * Default Python path from application
    * Change default buffer size to 16KiB
    * Some changes - obsolete, but commit before move to git
    * Python 3 pre-support, uWsgi server detection
    * http HEAD method supported

==== 20121130 ====
    * Webmaster mail bug fix
    * Logging bug fix
    * Poorwsgi could return files or directory index, so no dispatch_table.py
      could not be error
    * Poorhttp is simple wsgi server
    * rename http to phttp
    * Document Listing and get file support
    * users handler error calling
    * Bug fix
    * Environment fix
    * Flushing buffer bug fix
    * Some bug fix for run with uWsgi
    * Poorhttp is only wsgi server now.
    * And poorwsgi is python wsgi framework which coud be connect with anotger
      wsgi servers.
    * Method setreq is pre_process now.
    * Another post_process method is available.
    * Default handler as default_handler is available for other uri which is not
      in handlers list.
    * Read method for request in poorhttp.
    * Cookie bug fix with expire time and multiple cookie header support in
      poorhttp
    * fce support for getlist FieldStorage method
    * Directory listing, more compatible sendfile method and default it works
      html page.
    * Example is move to /app as default 'it works' example code.

==== 20120211 ====
    * File listing support as default handler for directory if new config
      option index is enabled.
    * Little bugfix with document config option.

==== 20111208 ====
    * convertor in FieldStorage
    * html error update
    * Doxygen support
    * example code
    * comments and documentation
    * bug fixes

==== 20100729 ====
    * apache compatibility
    * single / forking / thrading mode
    * bugfixing and error handlers captching and loging
    * more status codes

==== 20091130 ====
    * cookie session id is generate from expirydate by crypting
    * new method renew in cookie session

==== 20091126 ====
    * new configurable value server secret key added
    * new function hidden in session module for text crypting
    * handled config error exception
    * bug fix in loging
