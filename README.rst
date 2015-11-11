.. image:: https://img.shields.io/pypi/dm/PoorWSGI.svg
    :target: https://pypi.python.org/pypi/poorwsgi/
    :alt: Download this month

.. image:: https://img.shields.io/pypi/v/PoorWSGI.svg
    :target: https://pypi.python.org/pypi/poorwsgi/
    :alt: Latest version

.. image:: https://img.shields.io/pypi/pyversions/PoorWSGI.svg
    :target: https://pypi.python.org/pypi/poorwsgi/
    :alt: Supported Python versions

.. image:: https://img.shields.io/pypi/status/PoorWSGI.svg
    :target: https://pypi.python.org/pypi/poorwsgi/
    :alt: Development Status

.. image:: https://img.shields.io/pypi/l/PoorWSGI.svg
    :target: https://pypi.python.org/pypi/poorwsgi/
    :alt: License

Poor WSGI for Python
====================

Poor WSGI for Python is light WGI connector with uri routing between WSGI server
and your application. The simplest way to run and test it looks like that:

.. code-block:: python

    from wsgiref.simple_server import make_server
    from poorwsgi import Application

    app = Application('test')

    @app.route('/test')
    def root_uri(req):
        return 'Hello world'

    if __name__ == '__main__':
        httpd = make_server('127.0.0.1', 8080, app)
        httpd.serve_forever()

You can use python wsgiref.simple_server for test it:

::
    ~$ python simple.py

For more information see
`Project homepage <http://poorhttp.zeropage.cz/poorwsgi.html>`_
