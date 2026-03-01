About PoorWSGI
==============
PoorWSGI for Python is a lightweight WSGI connector with URI routing between the WSGI
server and your application. It has a request object similar to mod_python,
which is passed to all URI or HTTP state handlers. The simplest way to run and
test it with wsgiref.simple_server looks like this:

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

It has basic error pages like 403, 404, 405, 500, or 501. A 500 internal server
error will have debug output if poor_Debug is set. Additionally, there is a special debug page
on the ``/debug-info`` URI, which is also available when poor_Debug is set.

.. code:: sh

    ~$ poor_Debug=On python simple.py

PoorWSGI has some functions that you can use as a real HTTP server, which can
send files with the correct MIME type from disk, or generate directory listings.
See the Configuration section for more info.

.. code:: sh

    ~$ poor_DocumentRoot=./web poor_DocumentIndex=On python simple.py

The Story
=========
Once upon a time, there was a King. Or there was a Prince. Oh, maybe, there wasn't a
prince, but probably there was a Programmer, hmm, okay, a programmer. And this
programmer knew Apache's mod_python. Yes, it was a very, very bad paragon, but
before Python, he was programming in PHP. So mod_python was a big movement in the
right direction at that time.

He was finding out how he could write and host Python applications on a server.
And as he knew some closed-source framework that worked correctly, he wrote
another similar one for his own use. That is the basis of Poor Publisher. But WSGI was
coming, so he had an idea to write a new backend for his applications. That
is the basis of Poor HTTP and PoorWSGI.

Sometimes, Poor HTTP and PoorWSGI were one project. It was a better way, but
that wasn't the right way. After some time, he divided these two projects into
PoorWSGI and Poor HTTP projects. But there was a flawed concept in the PoorWSGI
framework, which wasn't a framework in fact. So he looked for other projects and
saw how nice it could be to create a WSGI application for the user. That is when
PoorWSGI was rewritten into library-type code, and the application became a
callable class with some nice routing methods and decorators.

This is the story of one programmer and his WSGI framework, which is not a
framework in fact, because it only handles URI requests with some mod_python
compatibility layer. As you can see, there are several ways this project can
evolve. Its author, the programmer, uses it on his projects, and it would be
very nice if there were more programmers than just him who used this little
project. Let's call it a WSGI connector.

If you have any questions, proposals, bug fixes, text corrections, or any
other matters, please send me an email to *mcbig at zeropage.cz*, or you can
create an issue on GitHub: https://github.com/PoorHttp/PoorWSGI/issues.
Thank you so much.

ChangeLog
=========
For release history or differences between releases, you can use git diff, diff
log, the git2cl tool, or consult the ChangeLog from the source code or on the Git
repository's web page. See:

    https://github.com/PoorHttp/PoorWSGI/blob/master/doc/ChangeLog

Examples
========
These are published application test files. You can download them, study them,
test them, or use them as you wish. See:

**http_digest.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/http_digest.py
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/test.digest

**large_file.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/large_file.py

**put_file.py**

    Example of uploading a file via the PUT method, similar to WebDAV.

    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/put_file.py

**openapi3.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/openapi3.py
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/openapi.json

**simple.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/simple.py

**websocket.py**
    https://github.com/PoorHttp/PoorWSGI/blob/master/examples/websocket.py
