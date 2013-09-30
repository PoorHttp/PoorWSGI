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
TODO: jinja:
    * TODO, FIXME, XXX highlight
=== Install ===
    * sourceforge tarbal
    * git download
    * pip install
=== Configuration ===
    * poorwsgi config variables
    * poorwsgi example config
    * uWsgi example config

== Tutorial ==
    * return object (generatin content)
    * forms input
    * headers (session)
    * routes
    * http state / default handler

== Few word on end ==
    * kde / proc se vzalo tu se vzalo poorwsgi
    * changelog
