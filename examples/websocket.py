"""WebSocket example.

to run with uWSGI (uWSGI needs SSL to working websockets):

.. code:: sh

    uwsgi --http-socket localhost:8080 \
            --http-raw-body \
            --gevent 100 \
            --wsgi-file examples/websocket.py

without uWsgi WSocket package is used:

.. code:: sh

   pip install WSocket

to proxy with nginx:

.. code:: nginx

    location /ws {
        proxy_pass              http://localhost:8080/ws;
        proxy_http_version      1.1;
        proxy_set_header        Upgrade $http_upgrade;
        proxy_set_header        Connection "Upgrade";
    }

Curl test:

.. code:: sh

    curl -i -N -H "Connection: Upgrade" \
            -H "Upgrade: websocket" \
            -H "Origin: http://localhost" \
            -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
            http://localhost:8080/ws

"""
# pylint: disable=consider-using-f-string
# pylint: disable=duplicate-code

from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
from sys import path as python_path
from os import path
from time import strftime
from secrets import choice
from types import MethodType

import logging as log

python_path.insert(0, path.abspath(
    path.join(path.dirname(__file__), path.pardir)))

# pylint: disable=wrong-import-position
from poorwsgi import Application  # noqa
from poorwsgi.response import Declined  # noqa

try:
    import uwsgi  # type: ignore

    # pylint: disable=invalid-name
    WebSocketError = OSError

    def WSocketApp(var):  # noqa: N802
        """Compatible with wsocket WSocketApp"""
        return var

    class WebSocket():
        """Compatibility class."""
        # pylint: disable=no-self-use

        def __init__(self):
            uwsgi.websocket_handshake()

        def receive(self):
            """Receive message from websocket."""
            return uwsgi.websocket_recv()

        def send(self, msg):
            """Send message to websocket."""
            uwsgi.websocket_send(msg)


except ModuleNotFoundError:
    # If uWsgi is not used, wsocket library handle websocket.

    uwsgi = None  # pylint: disable=invalid-name
    from wsocket import (WSocketApp,  # type: ignore
                         WebSocketError)


def get_websocket(environment):
    """Return websocket instace."""
    if uwsgi:
        return WebSocket()

    def receive(self):
        """uWsgi returns bytes."""
        string = self.receive_str()
        if string is None:
            raise WebSocketError("Socket was closed.")
        return string.encode('utf-8')

    obj = environment.get("wsgi.websocket")
    obj.receive_str = obj.receive
    obj.receive = MethodType(receive, obj)

    return environment.get("wsgi.websocket")


logger = log.getLogger()
logger.setLevel("DEBUG")

poor = Application(__name__)
poor.debug = True

app = application = WSocketApp(poor)


@poor.route('/')
def root(req):
    """Return Root (Index) page."""
    ws_scheme = 'wss' if req.scheme == 'https' else 'ws'

    return """
    <html>
      <head>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <title>WebSocket Example</title>
        <style>
          body {width:90%%; max-width:900px; margin:auto; padding-top:30px;}
          h1 {text-align: center; color: #707070;}
          #board { height: 480px; background:black; color:white;
            padding: 10px; overflow:auto;}
          #board > i {color: gray; font-family: monospace;}
          #board > b {color: lime;}
          #message {width: 80%%;}
        </style>
      </head>
      <body>
        <h1>WebSocket Example</h1>
        <div id="board"></div>
        <span id="state"></span>
        <form id="form">
          <input type="text" id="message"/>
          <input type="submit" value="Send"/>
        </form>
        <script>
          function record(msg){
            let board = document.getElementById('board');
            let html = board.innerHTML;
            board.innerHTML = html + '<br/>' + msg;
            board.scrollTo(0,board.scrollHeight);
          }
          function state(msg){
            let span = document.getElementById('state');
            span.innerHTML = msg;
          }

          var s = new WebSocket("%s://%s/ws");
          s.onopen = function() {
            state("Connected");
          };
          s.onmessage = function(e) {
              record(e.data);
          };

          s.onerror = function(e) {
              record("Error: "+ e);
          };

          s.onclose = function(e) {
            state("Disconnected");
          };

          let button = document.getElementById('form');
          button.addEventListener('submit', function(event) {
            let input = document.getElementById('message');
            s.send(input.value);
            input.value = '';
            event.preventDefault();
          });



        </script>
        <hr>
        <small>Copyright (c) 2021 Ondřej Tůma. See
          <a href="http://poorhttp.zeropage.cz">poorhttp.zeropage.cz</a>
        </small>
      </body>
    </html>""" % (ws_scheme, req.environ["HTTP_HOST"])


@poor.route('/ws')
def websocket(req):
    """Websocket endpoint"""
    answers = ("Hmm", "Yee", "Ok", "Really?", "Never mind", "You are best!",
               "😀", "😉", "☺", "😎", "👌", "👍", "🤔", "👏", "🤩", "...")
    try:
        wsock = get_websocket(req.environ)
        wsock.send("[<i>%s</i>] Hello" %
                   strftime("%Y-%m-%d %T"))
        while True:
            msg = wsock.receive().strip()
            if msg:
                wsock.send("[<i>%s</i>] <b>%s</b>" %
                           (strftime("%Y-%m-%d %T"), msg.decode('utf-8')))
                wsock.send("[<i>%s</i>] %s" %
                           (strftime("%Y-%m-%d %T"), choice(answers)))

    except WebSocketError:
        log.exception("Websocket was closed")
    return Declined()


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """This class is identical to WSGIServer but uses threads to handle
    requests by using the ThreadingMixIn. This is useful to handle weg
    browsers pre-opening sockets, on which Server would wait indefinitely.
    """

    multithread = True
    daemon_threads = True


if __name__ == '__main__':
    from wsocket import FixedHandler
    httpd = make_server('127.0.0.1', 8080, app,
                        ThreadingWSGIServer, FixedHandler)
    print("Starting to serve on http://127.0.0.1:8080")
    httpd.serve_forever()
