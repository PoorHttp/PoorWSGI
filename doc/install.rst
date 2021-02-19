Install
=======

Source from git
---------------

.. code:: sh

    ~$ git clone git@github.com:PoorHttp/PoorWSGI.git
    or
    ~$ git clone https://github.com/PoorHttp/PoorWSGI.git

    ~$ cd PoorWSGI
    ~$ pip3 install .

    # if you have jinja24doc and you want to install this html documentation
    ~$ python3 setup.py install_doc

Install from PyPI
-----------------
.. code:: sh

    ~$ pip3 install PoorWSGI

Unstable version
----------------
Developing of next version is pushed to ``master`` branch, which is default.
If you want to use this version, you must install it from git.

.. code:: sh

    ~$ git clone git@github.com:PoorHttp/PoorWSGI.git
    # or
    ~$ git clone https://github.com/PoorHttp/PoorWSGI.git

    ~$ cd PoorWSGI
    ~$ pip3 install .

Or you can download zip file from GitHub.

.. code:: sh

    ~$ wget https://github.com/PoorHttp/PoorWSGI/archive/master.zip
    ~$ unzip master.zip
    ~$ cd PoorWSGI-master
    ~$ pip3 install .

Configuration
=============
Poor WSGI is configured via environment variables with poor_* prefix.

Options
-------

poor_Debug
~~~~~~~~~~
If poor_Debug is ``On``, internal server error page have debug traceback and
``/debug-info`` page is activate.

poor_DocumentIndex
~~~~~~~~~~~~~~~~~~
If poor_DocumentRoot is set and poor_DocumentIndex is ``On``, poor WSGI can
generate document index from dictionary like real http servers. Default is
``Off``.

poor_DocumentRoot
~~~~~~~~~~~~~~~~~
pooor_DocumentRoot is dictionary, which is accessible files from. Files are
sent via FileResponse. Object returns opened file. And of course, before files
is set, right ``Content-Type`` from mime-type and ``Content-Length`` headers
are set.

poor_SecretKey
~~~~~~~~~~~~~~
If you want to use PoorSession class, as self-contained cookie, it is
**important** to set poor_SecretKey as pass phrase for hidden function, which is
call from PoorSession class. Default is not set, without that,
PoorSession.__init__ throw **RuntimeError**.

Poor HTTP server example
------------------------
Poor WSGI variables are system environment variables, which could be set in
``environ`` section in poorhttp.ini file. Only python file with ``application``
function or class must be set in predefined variable in ``http`` section:

.. code:: ini

    [http]
    ...
    # your main python file, where app, resp. application from wsgi module
    # is imported
    application = /srv/simple.py

    ...
    [environ]
    # debug - internal server errror page with traceback, debug-info page
    poor_Debug = Off
    poor_DocumentRoot = /srv/public
    poor_DocumentIndex = On

uWsgi server example
--------------------
uWsgi server have more choices how is configurable. Here is it's ini file,
which have one ``uwsgi`` section with ``wsgi-file`` variable, where we need
to set your main python file, and lots of env variables, which is use to set
environment variables.

.. code:: ini

    [uwsgi]
    ...
    # your main python file, where app, resp. application from wsgi module
    # is imported
    wsgi-file = /srv/simple.py

    # variables must be set without space between variable equation and value
    env = poor_Debug=On
    env = poor_DocumentRoot=/srv/public
    env = poor_SecretKey=MyApplication@Super!Secret?Password:-)
