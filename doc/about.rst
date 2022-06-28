About PoorWSGI
==============
PoorWSGI for Python is light WGI connector with uri routing between WSGI
server and your application. It have request object like in mod_python,
which is post to all uri or http state handlers. The simplest way to run and
test with wsgiref.simple_server it looks like that:

.. code:: python

    from wsgiref.simple_server import make_server
    from poorwsgi import Application

    app = Application('test')

    @app.route('/test')
    def root_uri(req):
        return 'Hello world'

    if __name__ == '__main__':
        httpd = make_server('127.0.0.1', 8080, app)
        httpd.serve_forever()

.. code:: sh

    ~$ python simple.py

It has base error pages like 403, 404, 405, 500 or 501. 500 internal server
error have debug output if poor_Debug is set. And there is special debug page
on ``/debug-info`` uri, which is available when poor_Debug is set too.

.. code:: sh

    ~$ poor_Debug=On python simple.py

Poor WSGI have some functions, to you can use as real http server, which could
send files with right mime-type from disk, or generate directory listing. See
Configuration section for more info.

.. code:: sh

    ~$ poor_DocumentRoot=./web poor_DocumentIndex=On python simple.py

The Story
=========
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
other things, please send me email to *mcbig at zeropage.cz* or you can
create issue on GutHub:
https://github.com/PoorHttp/PoorWSGI/issues Thank you so much.

ChangeLog
=========
For release history or difference of releases, you can use git diff, diff log,
git2cl tool or you can see ChangeLog from source code or on git repository
web. See:

    https://github.com/PoorHttp/PoorWSGI/blob/master/doc/ChangeLog

Examples
========
It is published application test files. You can download it, study it,
test or use it as you can. See:

**http_digest.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/http_digest.py
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/test.digest

**large_file.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/large_file.py

**put_file.py**

    Example of uploading file via PUT method like in WebDAV

    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/put_file.py

**openapi3.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/openapi3.py
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/openapi.json

**simple.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/simple.py

**websocket.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/websocket.py
