# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import shutil 
import logging
import unittest
import os

from kernel_gateway.gatewayapp import KernelGatewayApp, ioloop

from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest
from tornado.testing import gen_test
from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase
from tornado.escape import json_encode, json_decode, url_escape

class TestGatewayAppConfig(unittest.TestCase):
    def setUp(self):
        self.environ = os.environ

    def tearDown(self):
        os.environ = self.environ

    def test_config_env_vars(self):
        '''Env vars should be honored for traitlets.'''
        # Environment vars are always strings
        os.environ['KG_PORT'] = '1234'
        os.environ['KG_IP'] = '1.1.1.1'
        os.environ['KG_AUTH_TOKEN'] = 'fake-token'

        app = KernelGatewayApp()
        self.assertEqual(app.port, 1234)
        self.assertEqual(app.ip, '1.1.1.1')
        self.assertEqual(app.auth_token, 'fake-token')


class TestGatewayApp(AsyncHTTPTestCase, LogTrapTestCase):
    def get_new_ioloop(self):
        '''Use a global zmq ioloop for tests.'''
        return ioloop.IOLoop.current()

    def get_app(self):
        '''
        Instantiate the gateway app. Skip the http_server construction: the 
        test base class provides one for us.
        '''
        if hasattr(self, '_app'):
            return self._app
        app = KernelGatewayApp(log_level=logging.CRITICAL)
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
    def test_auth_token(self):
        '''All kernel endpoints should check the configured auth token.'''
        # Set token requirement
        app = self.get_app()
        app.settings['kg_auth_token'] = 'fake-token'

        # Request a kernel without the token
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}',
            raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Request with the token now
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}',
            headers={'Authorization': 'token fake-token'},
            raise_error=False
        )
        self.assertEqual(response.code, 201)

        kernel = json_decode(response.body)
        # Request kernel info without the token
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels/'+url_escape(kernel['id'])),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Now with it
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels/'+url_escape(kernel['id'])),
            method='GET',
            headers={'Authorization': 'token fake-token'},
            raise_error=False
        )
        self.assertEqual(response.code, 200)

        # Request websocket connection without the token
        ws_url = 'ws://localhost:{}/api/kernels/{}/channels'.format(
            self.get_http_port(),
            url_escape(kernel['id'])
        )
        # No option to ignore errors so try/except
        try:
            ws = yield websocket_connect(ws_url)
        except Exception as ex:
            self.assertEqual(ex.code, 401)

        # Now request the websocket with the token
        ws_req = HTTPRequest(ws_url, 
            headers={'Authorization': 'token fake-token'}
        )
        ws = yield websocket_connect(ws_req)
        ws.close()

    @gen_test
    def test_default_kernel(self):
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