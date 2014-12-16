#!/usr/local/bin/python2.7
# -*- coding: utf-8 -*-

__author__ = 'ogaidukov'


import gevent
from gevent import monkey
monkey.patch_all()
from gevent.lock import Semaphore
from gevent.queue import Queue
from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketServer, WebSocketApplication, Resource
import json
from flask import Flask

wsgi_app = Flask(__name__)
wsgi_app.debug = True

RESP_LISTEN_HOST = '0.0.0.0'
RESP_LISTEN_PORT = 9080
WS_LISTEN_HOST = '0.0.0.0'
WS_LISTEN_PORT = 9081
DEBUG = True

receivers = []
receivers_lock = Semaphore()


class WsServerApp(WebSocketApplication):
    def __init__(self, *args, **kwargs):
        self.queue = Queue()
        super(WsServerApp, self).__init__(*args, **kwargs)

    def on_open(self):
        with receivers_lock:
            receivers.append(self.queue)
        while True:
            val = self.queue.get()
            self.ws.send(val)

    def on_close(self, reason):
        print reason
        with receivers_lock:
            try:
                receivers.remove(self.queue)
            except ValueError:
                pass


@wsgi_app.route("/<status>/<site_team>/<int:player>/<number>")
def status_handler(status, site_team, player, number):
    if status not in ('online', 'offline'):
        return 'fail'
    try:
        site, team = [int(x) for x in site_team[:]]
    except ValueError:
        return 'fail'
    number = number[-4:]
    val_obj = {
        'action': status,
        'stend': site,
        'team': team,
        'player': player,
        'phone': number
    }
    val = json.dumps(val_obj)
    with receivers_lock:
        for q in receivers:
            q.put(val)
    return 'ok'


@wsgi_app.route("/digit/<site_team>/<int:player>/<int:digit>")
def digit_handler(site_team, player, digit):
    try:
        site, team = [int(x) for x in site_team[:]]
    except ValueError:
        return 'fail'
    val_obj = {
        'action': 'digit',
        'stend': site,
        'team': team,
        'player': player,
        'digit': digit
    }
    val = json.dumps(val_obj)
    with receivers_lock:
        for q in receivers:
            q.put(val)
    return 'ok'


def keep_alive():
    val = json.dumps({'keepalive': True})
    while True:
        with receivers_lock:
            for q in receivers:
                q.put(val)
        gevent.sleep(30)


def wsgi_responder():
    wsgi_app.debug = DEBUG
    server = WSGIServer((RESP_LISTEN_HOST, RESP_LISTEN_PORT), wsgi_app)
    server.serve_forever()


def websockets_server():
    server = WebSocketServer((WS_LISTEN_HOST, WS_LISTEN_PORT), Resource({'/': WsServerApp}), debug=DEBUG)
    server.serve_forever()


if __name__ == "__main__":
    gr = [
        gevent.spawn(websockets_server),
        gevent.spawn(wsgi_responder),
        gevent.spawn(keep_alive)
    ]
    gevent.joinall(gr)
