# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import shutil 

from kernel_gateway.gatewayapp import KernelGatewayApp, ioloop

from tempfile import mkdtemp
from tornado.gen import sleep
from tornado.websocket import websocket_connect
from tornado.testing import gen_test
from tornado.testing import AsyncHTTPTestCase
from tornado.escape import json_encode, json_decode, url_escape

class TestGatewayApp(AsyncHTTPTestCase):
    def setUp(self):
        '''Create a temporary directory for runtime files'''
        self.runtime_dir = mkdtemp()
        super(TestGatewayApp, self).setUp()

    def tearDown(self):
        '''Cleanup the temp runtime directory'''
        shutil.rmtree(self.runtime_dir)
        super(TestGatewayApp, self).tearDown()

    def get_new_ioloop(self):
        '''Use a global zmq ioloop for tests.'''
        return ioloop.IOLoop.current()

    def get_app(self):
        '''Instantiate the gateway app. Skip the http_server construction.'''
        app = KernelGatewayApp(
            runtime_dir=self.runtime_dir
        )
        app.init_configurables()
        app.init_webapp()
        return app.web_app

    @gen_test
    def test_startup(self):
        '''Root of kernels resource should be OK.'''
        response = yield self.http_client.fetch(self.get_url('/api/kernels'))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_headless(self):
        '''Other notebook resources should not exist.'''
        response = yield self.http_client.fetch(self.get_url('/api/contents'),
            raise_error=False)
        self.assertEqual(response.code, 404)
        response = yield self.http_client.fetch(self.get_url('/'),
            raise_error=False)
        self.assertEqual(response.code, 404)
        resp = yield self.http_client.fetch(self.get_url('/tree'),
            raise_error=False)
        self.assertEqual(response.code, 404)

    @gen_test
    def test_kernel(self):
        '''Default kernel should launch and accept commands.'''
        # Request a kernel
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}'
        )
        self.assertEqual(response.code, 201)

        # Connect to the kernel via websocket
        kernel = json_decode(response.body)
        ws_url = 'ws://localhost:{}/api/kernels/{}/channels'.format(
            self.get_http_port(),
            url_escape(kernel['id'])
        )
        ws = yield websocket_connect(ws_url)

        # Send a request for kernel info
        ws.write_message(json_encode({
            'header': {
                'username': '',
                'version': '5.0',
                'session': '',
                'msg_id': 'fake-msg-id',
                'msg_type': 'kernel_info_request'
            },
            'parent_header': {},
            'channel': 'shell',
            'content': {},
            'metadata': {},
            'buffers': {}
        }))

        # Assert the reply comes back. Test will timeout if this hangs.
        for _ in range(3):
            msg = yield ws.read_message()
            msg = json_decode(msg)
            if(msg['msg_type'] == 'kernel_info_reply'):
                break
        else:
            self.assert_(False, 'never received kernel_info_reply')
        ws.close()