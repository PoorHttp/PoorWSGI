
from sha import sha
from random import random
from time import localtime
from traceback import format_exception
from os import name as osname

import types, sys, re, os

_httpUrlPatern = re.compile(r"^(http|https):\/\/")

class Ok:
    """
    Standard http response
    """
    def __init__(self, content, status = 200,
                                content_type = 'text/html',
                                charset = 'utf-8',
                                header = []):
        
        if not type(content) in [types.ListType, types.TupleType]:
            content = [content]
        self.content = content
        
        if type(header) != types.ListType:
            header = [header]
        self.header = header

        if content_type:
            self.header = [
                ('Server', 'Poor Http (%s)' % osname),
                ('X-Powered-By', 'Python'),
                #('Content-Type', '%s; charset=%s' % (content_type, charset))
                ('Content-Type', '%s' % content_type),
            ] + self.header

        self.status = status
    #enddef

#endclass

class NotFound(Ok):
    def __init__(self, req):
        content = [
            "<html>\n",
            "  <head>\n",
            "    <title>404 - Page Not Found</title>\n",
            "    <style>\n",
            "      body {width: 80%; margin: auto; padding-top: 30px;}\n",
            "      h1 {text-align: center; color: #707070;}\n",
            "      p {text-indent: 30px; margin-top: 30px; margin-bottom: 30px;}\n",
            "    </style>\n",
            "  <head>\n",
            "  <body>\n",
            "    <h1>404 - Page Not Found</h1>\n",
            "    <p>Your reqeuest <code>%s</code> was not found.</p>" % req.path,
            "    <hr>\n",
            "    <small><i>webmaster: %s </i></small>\n" % req.webmaster ,
            "  </body>\n",
            "</html>"

        ]

        Ok.__init__(self,
                    content,
                    status = 404,
                    content_type = 'text/html')
    #enddef

#endclass

class InternalServerError(Ok):
    """
    This class call error log in init. When is not used, errors will
    not be loged. See code.
    """
    def __init__(self, req):
        traceback = format_exception(sys.exc_type,
                                     sys.exc_value,
                                     sys.exc_traceback)
        traceback = ''.join(traceback)
        req.log.error(traceback, req.remote_host)
        traceback = traceback.split('\n')
        
        content = [
            "<html>\n",
            "  <head>\n",
            "    <title>500 - Internal Server Error</title>\n",
            "    <style>\n",
            "      body {width: 80%; margin: auto; padding-top: 30px;}\n",
            "      pre .line1 {background: #e0e0e0}\n",
            "    </style>\n",
            "  <head>\n",
            "  <body>\n",
            "    <h1>500 - Internal Server Error</h1>\n",
        ]

        if req.log.debug:
            content += [
                "    <h2> Exception Traceback</h2>\n",
                "    <pre>",
            ]

            # Traceback
            for i in xrange(len(traceback)):
                content += '<div class="line%s">%s</div>' % \
                            ( i % 2, traceback[i])

            content += [
                "    </pre>\n",
                "    <hr>\n",
                "    <small><i>Poor Http / %s, Python / %s, webmaster: %s </i></small>\n" % \
                        (req.server_version,
                         sys.version.split(' ')[0],
                         req.webmaster),
            ]
        else:
            content += [
                "    <hr>\n",
                "    <small><i>webmaster: %s </i></small>\n" % req.webmaster ,
            ]

        #endif
        
        content += [
            "  </body>\n",
            "</html>"
        ]

        Ok.__init__(self,
                    content,
                    status = 500,
                    content_type = 'text/html')
    #enddef

#endclass

class Redirect(Ok):
    """
    Redirect server request to url via 302 server status.
    """
    def __init__(self, req, url, header = []):
        self.url = url
        
        scheme = req.environ.get('wsgi.url_scheme')
        host = req.environ.get('HTTP_HOST')

        if not _httpUrlPatern.match(url):
            url = "%s://%s%s" % (scheme, host, url)

        Ok.__init__(self,
                    content = [],
                    header = [('Location', url)] + header,
                    status = 302,
                    content_type = None)

    #enddef
#endclass

class File(Ok):
    """
    Returns file with content_type detect from server configuration or
    application/octet-stream.
    """
    def __init__(self, req, file):
        bin = []
        bf = os.open(file, os.O_RDONLY)
        data = os.read(bf, 1024)
        while data != '':
            bin.append(data)
            data = os.read(bf, 1024)
        #endwhile
        os.close(bf)

        ext = os.path.splitext(file)
        if req.cfg.has_option('mime-type', ext[1][1:]):
            content_type = req.cfg.get('mime-type', ext[1][1:])
        else:
            content_type = 'application/octet-stream'
        #endif
        Ok.__init__(self,
                    content = bin,
                    content_type = content_type)
    #enddef
#endclass
