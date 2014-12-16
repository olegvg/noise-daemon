#!/usr/local/bin/python2.7
# -*- coding: utf-8 -*-
from __future__ import division

__author__ = 'ogaidukov'

import os
import errno
from socket import error
from array import array as py_array
import gevent
from gevent.lock import Semaphore
from gevent.queue import Queue
from gevent.server import StreamServer
from numpy import array as np_array, mean, absolute
from numpy.fft import fft

WORKER_ASSIGNMENTS = [
    ('/opt/noise_daemon/loc1phone1.PCMA', 'loc1player1'),
    ('/opt/noise_daemon/loc1phone2.PCMA', 'loc1player2'),
    ('/opt/noise_daemon/loc2phone1.PCMA', 'loc2player1'),
    ('/opt/noise_daemon/loc2phone2.PCMA', 'loc2player2'),
    ('/opt/noise_daemon/loc3phone1.PCMA', 'loc3player1'),
    ('/opt/noise_daemon/loc3phone2.PCMA', 'loc3player2'),
    ('/opt/noise_daemon/loc4phone1.PCMA', 'loc4player1'),
    ('/opt/noise_daemon/loc4phone2.PCMA', 'loc4player2'),
    ('/opt/noise_daemon/loc5phone1.PCMA', 'loc5player1'),
    ('/opt/noise_daemon/loc5phone2.PCMA', 'loc5player2')
]
CHUNK = 1000    # 8000 samples per second thus we use 0.125 second chunk
BASE = 600
DIVIDER = 70
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 8080


receivers = []
receivers_lock = Semaphore()


def carry_stream(pipe_name, string_prefix, chunk, base, divider):
    os_fd = os.open(pipe_name, os.O_RDONLY | os.O_NONBLOCK)
    while True:
        snd_buffer = py_array('b')
        while True:
            try:
                snd_buffer.fromstring(os.read(os_fd, chunk - len(snd_buffer)))
            except OSError as err:
                if err.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
            if len(snd_buffer) == chunk:
                break
            gevent.sleep(0.025)
        prepared_counts = np_array(absolute(snd_buffer))
        fourier_array = fft(prepared_counts)
        avg = mean(absolute(fourier_array))
        noise_level = int(abs(round((avg - base) / divider)))       # 'base' and 'divider' are empirical coefficients,
                                                                    # but take in mind that 'noise_level' must be
                                                                    # in 0...9 interval
        with receivers_lock:
            for q in receivers:
                q.put("{}:{}\n".format(string_prefix, noise_level))
        gevent.sleep(0.01)
    #os.close(os_fd)    # it implicitly done during the process killing


def handle(socket, address):
    with receivers_lock:
        queue = Queue()
        receivers.append(queue)
    while True:
        val = queue.get()
        try:
            socket.send(val)
        except error:
            with receivers_lock:
                receivers.remove(queue)
            socket.close()
            break


if __name__ == "__main__":
    for task in WORKER_ASSIGNMENTS:
        gevent.spawn(carry_stream, task[0], task[1], CHUNK, BASE, DIVIDER)
        # Process resources freeing is implicitly done during the process killing so we don't need to store
        # greenlet objects to do 'gevent.joinall'
    server = StreamServer((LISTEN_HOST, LISTEN_PORT), handle)
    server.serve_forever()
