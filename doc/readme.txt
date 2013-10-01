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


=== Input variables / Forms ===

=== Headers and Sessions ===

== Few word on end ==
    * kde / proc se vzalo tu se vzalo poorwsgi
    * changelog
