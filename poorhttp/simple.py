# -*- coding: utf-8 -*-

from wsgiref.headers import Headers
from base64 import decodestring

import os

class Application:
    def __init__(self):
        self.routes = {
            '/'             : self.root,
            '/debug'        : self.debug,
            '/favicon.ico'  : self.favicon,
        }


    def __call__(self, environ, start_response):
        method  = environ.get('REQUEST_METHOD')
        uri     = environ.get('PATH_INFO')

        if method not in ('HEAD', 'GET', 'POST'):
            return self.method_not_allowed(environ, start_response)

        if uri not in self.routes:
            return self.page_not_found(environ, start_response)

        return self.routes[uri](environ, start_response)

    
    def get_headers(self, environ):
        tmp = []
        for key, val in environ.items():
            if key[:5] == 'HTTP_':
                key = '-'.join(map(lambda x: x.capitalize() ,key[5:].split('_')))
                tmp.append((key, val))
        return Headers(tmp)


    def get_crumbnav(self, environ):
        navs = [environ.get('HTTP_HOST')]
        uri = environ.get('PATH_INFO')
        if uri == '/':
            navs.append('<b>/</b>')
        else:
            navs.append('<a href="/">/</a>')
            navs.append('<b>%s</b>' % uri)
        return " &raquo; ".join(navs)

    
    def root(self, environ, start_response):
        buff = [
            "<html>",
            "<head>",
            '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
            "<title>Simple WSGI Example Application</title>",
            "</head>",
            "<body>",
            "<h1>Simple WSGI Example Application</h1>",
            self.get_crumbnav(environ),
            "<ul>",
            '<li><a href="/">/</a> - This Page</li>',
            '<li><a href="/debug">/debug</a> - Debug Page</li>',
            '<li><a href="/no-page">/no-page</a> - No Exist Page</li>',
            "</ul>",
            "<hr>",
            "<small>Copyright (c) 2013 Ondřej Tůma. See ",
            '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a></small>.',
            "</body>",
            "</html>"
        ]

        response_headers = [('Content-type', 'text/html'),
                            ('X-Application', 'Simple')]
        start_response("200 OK", response_headers)
        return [line + '\n' for line in buff]


    def debug(self, environ, start_response):
        headers = self.get_headers(environ)
        buff = [
            "<html>",
            "<head>",
            '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
            "<title>Debug Page</title>",
            "<style>",
            "table { width: 100%; font-family: monospace; }",
            "td { word-break:break-word; }",
            "td:first-child { white-space: nowrap; word-break:keep-all; }",
            "tr:hover { background: #e0e0e0; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Server/Application Debug Page</h1>",
            self.get_crumbnav(environ),
            "<h2>Browser Headers</h2>",
            "<table>"
        ] + [ "<tr><td>%s:</td><td>%s</td>" % \
                                (key, val) for key, val in headers.items()
        ] + ["</table>",
            "<h2>Application Environment</h2>",
            "<table>"
        ] + [ "<tr><td>%s:</td><td>%s</td>" % \
                                (key, val) for key, val in environ.items()
        ] + ["</table>",
            "<hr>",
            "<small>Copyright (c) 2013 Ondřej Tůma. See ",
            '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a></small>.',
            "</body>",
            "</html>"
        ]

        response_headers = [('Content-type', 'text/html'),
                            ('X-Application', 'Simple')]
        start_response("200 OK", response_headers)
        return [line + '\n' for line in buff]
    

    def favicon(self, environ, start_response):
        icon = """
AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAD///8A////AP///wD///8AFRX/Bw8P/24ICP/IAgL/7wAA/+oAAP/GAAD/bQAA/wj///8A
////AP///wD///8A////AP///wD///8A////AB4e/4gYGP//ERH//wsL//8EBP//AAD/1QAA/6AA
AP+C////AP///wD///8A////AP///wD///8A////AP///wAnJ//dISH//xsb//8UFP//Dg7//wcH
/9cBAf+kAAD/1f///wD///8A////AP///wD///8A////AP///wD///8AMTH/4Coq//8kJP//HR3/
/xcX/7AQEP+wCgr/sAMD/5T///8A////AP///wD///8AAHo+BwB3O4AAczjSAHA1jTo6/+AzM///
LS3//yYm//8gIP/YGRn/2BMT/9gNDf/YBgb/2AAA/9UAAP+HAAD/BgB9QGwAej3/AHY6/wBzOKg9
Pf/fPDz//zY2//8vL///KSn//yMj//8cHP//Fhb//w8P//8JCf//AgL//wAA/2oAgELGAH1A/wB5
Pf8AdjrkPD79nz09//89Pf//OTn//zIy//8sLP//JSX//x8f//8YGP//EhL//wwM//8FBf/HAINF
6wCAQv8AfD//AHk8/wtrXYw8PvqUPT3/zz09/9A7O//QNTX/0C4u//koKP//IiL//xsb//8VFf//
Dg7/7wCHR+8Ag0T/AH9B/wB8P/8AeDz/AHU57ABxN7gAbjS4AGoxuABpMLcKYVSFLzP3nysr//8k
JP//Hh7//xcX/+sAiknKAIZH/wCDRP8Af0H/AHs+/wB4PP8AdDn/AHE2/wBtM/8AajH/AGkw/wVl
QZE0NP/xLS3//ycn//8gIP/JAI1MagCJSf8Ahkb/AIJD/wB/Qf8Aez7/AHg7/wB0Of8AcDb/AG0z
/wBpMP8AaTDVPT3/sjY2//8wMP//Kir/egCQTgIAjEuGAIlJ1QCFRugAgkPoAH5A6AB7PugAdzvo
AHQ4/wBwNf8AbDP/AGkw1z09/589Pf/lOTn/mzMz/w7///8A////AP///wD///8AAIVFhQCBQ5gA
fkCYAHo9mAB3O/8Aczj/AG81/wBsMtj///8A////AP///wD///8A////AP///wD///8A////AACI
SN8AhEW0AIFC5wB9QP8Aej3/AHY6/wBzN/8AbzXX////AP///wD///8A////AP///wD///8A////
AP///wAAi0q1AIdHhwCERc4AgEL/AH0//wB5PP8Adjr/AHI3k////wD///8A////AP///wD///8A
////AP///wD///8AAI5NJQCKSpkAh0fhAINE9wCAQvQAfD/fAHk8jwB1ORT///8A////AP///wD/
//8A/D8AAPAPAADwDwAA8A8AAIABAACAAQAAAAAAAAAAAAAAAAAAAAAAAIABAACAAQAA8A8AAPAP
AADwDwAA+B8AAA==
"""
        response_headers = [('Content-type', 'image/vnd.microsoft.icon'),
                            ('X-Application', 'Simple')]
        start_response("200 OK", response_headers)
        return  [decodestring(icon)]

    def method_not_allowed(self, environ, start_response):
        method = environ.get('REQUEST_METHOD')

        errors = environ.get('wsgi.errors')
        errors.write("Method %s is not allowed for this request" % method)
        
        buff = [
            "<html>",
            "<head>",
            '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
            "<title>405 - Method Not Allowed</title>",
            "</head>",
            "<body>",
            "<h1>405 - Method Not Allowed</h1>",
            self.get_crumbnav(environ),
            "<p>Method %s is not allowed for this request</p>" % method,
            "<hr>",
            "<small>Copyright (c) 2013 Ondřej Tůma. See ",
            '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a></small>.',
            "</body>",
            "</html>"
        ]

        response_headers = [('Content-type', 'text/html'),
                            ('X-Application', 'Simple')]
        start_response("405 Method Not Allowed", response_headers)
        return [line + '\n' for line in buff]


    def page_not_found(self, environ, start_response):
        uri = environ.get('PATH_INFO')

        errors = environ.get('wsgi.errors')
        errors.write("Your request %s was not found." % uri)
        
        buff = [
            "<html>",
            "<head>",
            '<meta http-equiv="content-type" content="text/html; charset=utf-8"/>',
            "<title>404 - Page Not Found</title>",
            "</head>",
            "<body>",
            "<h1>405 - Page Not Found</h1>",
            self.get_crumbnav(environ),
            "<p>Your request %s was not found.\n</p>" % uri,
            "<hr>",
            "<small>Copyright (c) 2013 Ondřej Tůma. See ",
            '<a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a></small>.',
            "</body>",
            "</html>"
        ]

        response_headers = [('Content-type', 'text/html'),
                            ('X-Application', 'Simple')]
        start_response("405 Method Not Allowed", response_headers)
        return [line + '\n' for line in buff]


application = Application()
