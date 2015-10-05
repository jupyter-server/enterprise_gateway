# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import time
import requests
from contextlib import contextmanager
from threading import Thread, Event
from unittest import TestCase

from tornado.ioloop import IOLoop

from kernel_gateway.gatewayapp import KernelGatewayApp

MAX_WAITTIME = 5    # seconds to wait for notebook server to start
POLL_INTERVAL = 0.1 # time between attempts

class GatewayTestBase(TestCase):
    '''
    A base class for tests that need a running gateway.
    Borrowed from jupyter/notebook.
    '''

    port = 12341

    @classmethod
    def base_url(cls):
        return 'http://localhost:%d' % cls.port

    @classmethod
    def wait_until_alive(cls):
        '''Wait for the server to be alive'''
        url = cls.base_url() + '/api/kernels'
        for _ in range(int(MAX_WAITTIME/POLL_INTERVAL)):
            try:
                requests.get(url)
            except Exception as e:
                time.sleep(POLL_INTERVAL)
            else:
                return

        raise TimeoutError("The notebook server didn't start up correctly.")
    
    @classmethod
    def wait_until_dead(cls):
        '''Wait for the server process to terminate after shutdown'''
        cls.gateway_thread.join(timeout=MAX_WAITTIME)
        if cls.gateway_thread.is_alive():
            raise TimeoutError("Undead notebook server")

    @classmethod
    def setUpClass(cls):
        app = cls.gateway = KernelGatewayApp(
            port=cls.port
        )
        
        # clear log handlers and propagate to root for nose to capture it
        # needs to be redone after initialize, which reconfigures logging
        app.log.propagate = True
        app.log.handlers = []
        app.initialize(argv=[])
        app.log.propagate = True
        app.log.handlers = []
        started = Event()
        def start_thread():
            loop = IOLoop.current()
            loop.add_callback(started.set)
            try:
                app.start()
            finally:
                # set the event, so failure to start doesn't cause a hang
                started.set()
        cls.gateway_thread = Thread(target=start_thread)
        cls.gateway_thread.start()
        started.wait()
        cls.wait_until_alive()

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()
