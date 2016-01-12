# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import logging
import unittest
import os
import sys
import json

from kernel_gateway.gatewayapp import KernelGatewayApp, ioloop
from jupyter_client.kernelspec import NoSuchKernel

from tornado.gen import coroutine, Return
from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest
from tornado.testing import gen_test
from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase
from tornado.escape import json_encode, json_decode, url_escape

RESOURCES = os.path.join(os.path.dirname(__file__), 'resources')

class TestGatewayAppConfig(unittest.TestCase):
    def setUp(self):
        self.environ = dict(os.environ)

    def tearDown(self):
        os.environ = self.environ

    def test_config_env_vars(self):
        '''Env vars should be honored for traitlets.'''
        # Environment vars are always strings
        os.environ['KG_PORT'] = '1234'
        os.environ['KG_IP'] = '1.1.1.1'
        os.environ['KG_AUTH_TOKEN'] = 'fake-token'
        os.environ['KG_ALLOW_CREDENTIALS'] = 'true'
        os.environ['KG_ALLOW_HEADERS'] = 'Authorization'
        os.environ['KG_ALLOW_METHODS'] = 'GET'
        os.environ['KG_ALLOW_ORIGIN'] = '*'
        os.environ['KG_EXPOSE_HEADERS'] = 'X-Fake-Header'
        os.environ['KG_MAX_AGE'] = '5'
        os.environ['KG_BASE_URL'] = '/fake/path'
        os.environ['KG_MAX_KERNELS'] = '1'
        os.environ['KG_SEED_URI'] = 'fake-notebook.ipynb'
        os.environ['KG_PRESPAWN_COUNT'] = '1'
        os.environ['KG_DEFAULT_KERNEL_NAME'] = 'fake_kernel'
        os.environ['KG_LIST_KERNELS'] = 'True'
        os.environ['KG_ALLOW_NOTEBOOK_DOWNLOAD'] = 'True'

        app = KernelGatewayApp()

        self.assertEqual(app.port, 1234)
        self.assertEqual(app.ip, '1.1.1.1')
        self.assertEqual(app.auth_token, 'fake-token')
        self.assertEqual(app.allow_credentials, 'true')
        self.assertEqual(app.allow_headers, 'Authorization')
        self.assertEqual(app.allow_methods, 'GET')
        self.assertEqual(app.allow_origin, '*')
        self.assertEqual(app.expose_headers, 'X-Fake-Header')
        self.assertEqual(app.max_age, '5')
        self.assertEqual(app.base_url, '/fake/path')
        self.assertEqual(app.max_kernels, 1)
        self.assertEqual(app.seed_uri, 'fake-notebook.ipynb')
        self.assertEqual(app.prespawn_count, 1)
        self.assertEqual(app.default_kernel_name, 'fake_kernel')
        self.assertEqual(app.list_kernels, True)
        self.assertEqual(app.allow_notebook_download, True)

class TestGatewayAppBase(AsyncHTTPTestCase, LogTrapTestCase):
    def tearDown(self):
        if self.app:
            self.app.shutdown()
        super(TestGatewayAppBase, self).tearDown()

    def get_new_ioloop(self):
        '''Use a global zmq ioloop for tests.'''
        return ioloop.IOLoop.current()

    def get_app(self):
        '''Returns a tornado.web.Application for system tests.'''
        if hasattr(self, '_app'):
            return self._app
        self.app = KernelGatewayApp(log_level=logging.CRITICAL)
        self.setup_app()
        self.app.init_configurables()
        self.app.init_webapp()
        return self.app.web_app

    def setup_app(self):
        '''
        Override to configure KernelGatewayApp instance before initializing
        configurables and the web app.
        '''
        pass

    @coroutine
    def spawn_kernel(self, kernel_body='{}'):
        '''
        Code to spawn a kernel and return a websocket connection to it.
        '''
        # Request a kernel
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body=kernel_body
        )
        self.assertEqual(response.code, 201)

        # Connect to the kernel via websocket
        kernel = json_decode(response.body)
        ws_url = 'ws://localhost:{}/api/kernels/{}/channels'.format(
            self.get_http_port(),
            url_escape(kernel['id'])
        )

        ws = yield websocket_connect(ws_url)
        raise Return(ws)

class TestGatewayApp(TestGatewayAppBase):
    @gen_test
    def test_startup(self):
        '''Root of kernels resource should be OK.'''
        self.app.web_app.settings['kg_list_kernels'] = True
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
    def test_config_bad_api_value(self):
        '''A ValueError should be raised on an unsupported KernelGatewayApp.api value'''
        def _set_api():
            self.app.api = 'notebook-gopher'
        self.assertRaises(ValueError, _set_api)

    @gen_test
    def test_auth_token(self):
        '''All server endpoints should check the configured auth token.'''
        # Set token requirement
        app = self.get_app()
        app.settings['kg_auth_token'] = 'fake-token'
        app.settings['kg_list_kernels'] = True

        # Requst API without the token
        response = yield self.http_client.fetch(
            self.get_url('/api'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Now with it
        response = yield self.http_client.fetch(
            self.get_url('/api'),
            method='GET',
            headers={'Authorization': 'token fake-token'},
            raise_error=False
        )
        self.assertEqual(response.code, 200)

        # Requst kernelspecs without the token
        response = yield self.http_client.fetch(
            self.get_url('/api/kernelspecs'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Now with it
        response = yield self.http_client.fetch(
            self.get_url('/api/kernelspecs'),
            method='GET',
            headers={'Authorization': 'token fake-token'},
            raise_error=False
        )
        self.assertEqual(response.code, 200)

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
        else:
            self.assert_(False, 'no exception raised')

        # Now request the websocket with the token
        ws_req = HTTPRequest(ws_url,
            headers={'Authorization': 'token fake-token'}
        )
        ws = yield websocket_connect(ws_req)
        ws.close()

    @gen_test
    def test_cors_headers(self):
        '''All kernel endpoints should respond with configured CORS headers.'''
        app = self.get_app()
        app.settings['kg_allow_credentials'] = 'false'
        app.settings['kg_allow_headers'] = 'Authorization,Content-Type'
        app.settings['kg_allow_methods'] = 'GET,POST'
        app.settings['kg_allow_origin'] = 'https://jupyter.org'
        app.settings['kg_expose_headers'] = 'X-My-Fake-Header'
        app.settings['kg_max_age'] = '600'
        app.settings['kg_list_kernels'] = True

        # Get kernels to check headers
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='GET'
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Credentials'], 'false')
        self.assertEqual(response.headers['Access-Control-Allow-Headers'], 'Authorization,Content-Type')
        self.assertEqual(response.headers['Access-Control-Allow-Methods'], 'GET,POST')
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://jupyter.org')
        self.assertEqual(response.headers['Access-Control-Expose-Headers'], 'X-My-Fake-Header')
        self.assertEqual(response.headers['Access-Control-Max-Age'], '600')
        self.assertEqual(response.headers.get('Content-Security-Policy'), None)

    @gen_test
    def test_max_kernels(self):
        '''Number of kernels should be limited.'''
        app = self.get_app()
        app.settings['kg_max_kernels'] = 1

        # Request a kernel
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}'
        )
        self.assertEqual(response.code, 201)

        # Request another
        response2 = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}',
            raise_error=False
        )
        self.assertEqual(response2.code, 402)

        # Shut down the kernel
        kernel = json_decode(response.body)
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels/'+url_escape(kernel['id'])),
            method='DELETE'
        )
        self.assertEqual(response.code, 204)

        # Try again
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}'
        )
        self.assertEqual(response.code, 201)

    @gen_test
    def test_get_api(self):
        '''Server should respond with the API version metadata.'''
        response = yield self.http_client.fetch(
            self.get_url('/api')
        )
        self.assertEqual(response.code, 200)
        info = json_decode(response.body)
        self.assertIn('version', info)

    @gen_test
    def test_get_kernelspecs(self):
        '''Server should respond with kernel spec metadata.'''
        response = yield self.http_client.fetch(
            self.get_url('/api/kernelspecs')
        )
        self.assertEqual(response.code, 200)
        specs = json_decode(response.body)
        self.assertIn('kernelspecs', specs)
        self.assertIn('default', specs)

    @gen_test
    def test_get_kernels(self):
        '''Server should respond with running kernel information.'''
        self.app.web_app.settings['kg_list_kernels'] = True
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels')
        )
        self.assertEqual(response.code, 200)
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 0)

        # Launch a kernel
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}'
        )
        self.assertEqual(response.code, 201)
        kernel = json_decode(response.body)

        # Check the list again
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels')
        )
        self.assertEqual(response.code, 200)
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 1)
        self.assertEqual(kernels[0]['id'], kernel['id'])

    @gen_test
    def test_kernel_comm(self):
        '''Default kernel should launch and accept commands.'''
        ws = yield self.spawn_kernel()

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

    @gen_test
    def test_default_kernel_name(self):
        '''The default kernel name should be used on empty requests.'''
        app = self.get_app()
        app.settings['kg_default_kernel_name'] = 'fake-kernel'
        # Request without an explicit kernel name
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='',
            raise_error=False
        )
        self.assertEqual(response.code, 500)
        self.assertTrue('raise NoSuchKernel' in str(response.body))

    @gen_test
    def test_enable_kernel_list(self):
        '''The listing of running kernels can be enabled.'''
        app = self.get_app()
        # default
        app.settings.pop('kg_list_kernels', None)
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            raise_error=False
        )
        self.assertEqual(response.code, 404)

        # set to True
        app.settings['kg_list_kernels'] = True
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
        )
        self.assertEqual(response.code, 200)
        self.assertTrue('[]' in str(response.body))

        # set to False
        app.settings['kg_list_kernels'] = False
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            raise_error=False
        )
        self.assertEqual(response.code, 404)

class TestFormatRequestCodeEscapedIntegration(TestGatewayAppBase):
    def setup_app(self):
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_format_request_code_escaped_integration(self):
        '''
        Quotes should be properly escaped in the request code
        '''

        #Test query with escaping of arguements and headers with multiple escaped quotes
        response = yield self.http_client.fetch(
            self.get_url('/hello/person?person=governor'),
            method='GET',
            headers={'If-None-Match': '\"\"9a28a9262f954494a8de7442c63d6d0715ce0998\"\"'},
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor\n', 'Unexpected body in response to GET.')

class TestPrespawnGatewayApp(TestGatewayAppBase):
    def setup_app(self):
        self.app.prespawn_count = 2

    @gen_test(timeout=10)
    def test_prespawn_count(self):
        '''Server should launch given number of kernels on start.'''
        self.app.web_app.settings['kg_list_kernels'] = True
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels')
        )
        self.assertEqual(response.code, 200)
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 2)

    def test_prespawn_max_conflict(self):
        '''
        Server should error if prespawn count is greater than max allowed
        kernels.
        '''
        app = KernelGatewayApp()
        app.prespawn_count = 3
        app.max_kernels = 2
        self.assertRaises(RuntimeError, app.init_configurables)

class TestRelocatedGatewayApp(TestGatewayAppBase):
    def setup_app(self):
        self.app.base_url = '/fake/path'

    @gen_test
    def test_base_url(self):
        '''Server should mount resources under configured base.'''
        self.app.web_app.settings['kg_list_kernels'] = True
        # Should not exist at root
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404)

        # Should exist under path
        response = yield self.http_client.fetch(
            self.get_url('/fake/path/api/kernels'),
            method='GET'
        )
        self.assertEqual(response.code, 200)

class TestSeedGatewayApp(TestGatewayAppBase):
    def setup_app(self):
        self.app.seed_uri = os.path.join(RESOURCES,
            'zen{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_seed(self):
        '''Kernel should have variables preseeded from notebook. Failures may be the result of networking problems.'''
        ws = yield self.spawn_kernel()

        # Print the encoded "zen of python" string, the kernel should have
        # it imported
        ws.write_message(json_encode({
            'header': {
                'username': '',
                'version': '5.0',
                'session': '',
                'msg_id': 'fake-msg-id',
                'msg_type': 'execute_request'
            },
            'parent_header': {},
            'channel': 'shell',
            'content': {
                'code': 'print(this.s)',
                'silent': False,
                'store_history': False,
                'user_expressions' : {}
            },
            'metadata': {},
            'buffers': {}
        }))

        # Read messages until we see the output from the print or hit the
        # test timeout
        while 1:
            msg = yield ws.read_message()
            msg = json_decode(msg)
            msg_type = msg['msg_type']
            parent_msg_id = msg['parent_header']['msg_id']
            if msg_type == 'stream' and parent_msg_id == 'fake-msg-id':
                content = msg['content']
                self.assertEqual(content['name'], 'stdout')
                self.assertIn('Gur Mra bs Clguba', content['text'])
                break

        ws.close()

class TestDownloadNotebookSource(TestGatewayAppBase):
    def setup_app(self):
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))
        self.app.allow_notebook_download = True

    @gen_test
    def test_download_notebook_source(self):
        '''
        Notebook source should exists under the path /_api/source
        when allow_notebook download is True
        '''
        response = yield self.http_client.fetch(
            self.get_url('/_api/source'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, "/_api/source did not correctly return the downloaded notebook")

class TestBlockedDownloadNotebookSource(TestGatewayAppBase):
    def setup_app(self):
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))
    @gen_test
    def test_blocked_download_notebook_source(self):
        '''
        Notebook source should not exist under the path /_api/source
        when allow_notebook download is False or not configured
        '''
        response = yield self.http_client.fetch(
            self.get_url('/_api/source'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404, "/_api/source did not block as allow_notebook_download is false")

class TestSeedGatewayAppKernelLanguageSupport(TestGatewayAppBase):
    def setup_app(self):
        self.app.prespawn_count = 1
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'zen{}.ipynb'.format(sys.version_info.major))
    @coroutine
    def spawn_kernel(self):
        ws = yield super(TestSeedGatewayAppKernelLanguageSupport, self).spawn_kernel(kernel_body=json.dumps({"name":"python{}".format(sys.version_info.major)}))
        raise Return(ws)

    @gen_test
    def test_seed_kernel_name_language_support(self):
        '''Python2 Kernel should have the correct name'''
        _, kernel_id = yield self.app.kernel_pool.acquire()
        kernel = self.app.kernel_manager.get_kernel(kernel_id)
        self.assertEqual(kernel.kernel_name,'python{}'.format(sys.version_info.major))

    @gen_test
    def test_seed_language_support(self):
        '''Python2 Kernel should have variables preseeded from notebook. Failures may be the result of networking problems.'''
        ws = yield self.spawn_kernel()
        if sys.version_info.major == 2:
            code = 'print this.s'
        else:
            code = 'print(this.s)'
        # Print the encoded "zen of python" string, the kernel should have
        # it imported
        ws.write_message(json_encode({
            'header': {
                'username': '',
                'version': '5.0',
                'session': '',
                'msg_id': 'fake-msg-id',
                'msg_type': 'execute_request'
            },
            'parent_header': {},
            'channel': 'shell',
            'content': {
                'code': code,
                'silent': False,
                'store_history': False,
                'user_expressions' : {}
            },
            'metadata': {},
            'buffers': {}
        }))

        # Read messages until we see the output from the print or hit the
        # test timeout
        while 1:
            msg = yield ws.read_message()
            msg = json_decode(msg)
            msg_type = msg['msg_type']
            parent_msg_id = msg['parent_header']['msg_id']
            if msg_type == 'stream' and parent_msg_id == 'fake-msg-id':
                content = msg['content']
                self.assertEqual(content['name'], 'stdout')
                self.assertIn('Gur Mra bs Clguba', content['text'])
                break

        ws.close()

class TestRemoteSeedGatewayApp(TestSeedGatewayApp):
    def setup_app(self):
        self.app.seed_uri = 'https://gist.githubusercontent.com/parente/ccd36bd7db2f617d58ce/raw/zen{}.ipynb'.format(sys.version_info.major)

class TestBadSeedGatewayApp(TestGatewayAppBase):
    def setup_app(self):
        self.app.seed_uri = os.path.join(RESOURCES,
            'failing_code{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_seed_error(self):
        '''
        Server should shutdown kernel and respond with error when seed notebook
        has an execution error.
        '''
        self.app.web_app.settings['kg_list_kernels'] = True
        # Request a kernel
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{}',
            raise_error=False
        )
        self.assertEqual(response.code, 500)

        # No kernels should be running
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='GET'
        )
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 0)

    def test_seed_kernel_not_available(self):
        '''
        Server should error because seed notebook requires a kernel that is not
        installed.
        '''
        app = KernelGatewayApp()
        app.seed_uri = os.path.join(RESOURCES, 'unknown_kernel.ipynb')
        self.assertRaises(NoSuchKernel, app.init_configurables)

class TestAPIGatewayApp(TestGatewayAppBase):
    def setup_app(self):
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
            'kernel_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_api_get_endpoint(self):
        '''GET HTTP method should be callable
        '''
        response = yield self.http_client.fetch(
            self.get_url('/hello'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello world\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_get_endpoint_with_path_param(self):
        '''GET HTTP method should be callable with a path param
        '''
        response = yield self.http_client.fetch(
            self.get_url('/hello/governor'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_get_endpoint_with_query_param(self):
        '''GET HTTP method should be callable with a query param
        '''
        response = yield self.http_client.fetch(
            self.get_url('/hello/person?person=governor'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_get_endpoint_with_multiple_query_params(self):
        '''GET HTTP method should be callable with multiple query params
        '''
        response = yield self.http_client.fetch(
            self.get_url('/hello/persons?person=governor&person=rick'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor, rick\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_put_endpoint(self):
        '''PUT HTTP method should be callable
        '''
        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='PUT',
            body='hola {}',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'PUT endpoint did not return 200.')

        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hola {}\n', 'Unexpected body in response to GET after performing PUT.')

    @gen_test
    def test_api_post_endpoint(self):
        '''POST endpoint should be callable
        '''
        expected = b'["Rick", "Maggie", "Glenn", "Carol", "Daryl"]\n'
        response = yield self.http_client.fetch(
            self.get_url('/people'),
            method='POST',
            body=expected.decode('UTF-8'),
            raise_error=False,
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.code, 200, 'POST endpoint did not return 200.')
        self.assertEqual(response.body, expected, 'Unexpected body in response to POST.')

    @gen_test
    def test_api_delete_endpoint(self):
        '''DELETE HTTP method should be callable
        '''
        expected = b'["Rick", "Maggie", "Glenn", "Carol", "Daryl"]\n'
        response = yield self.http_client.fetch(
            self.get_url('/people'),
            method='POST',
            body=expected.decode('UTF-8'),
            raise_error=False,
            headers={'Content-Type': 'application/json'}
        )
        response = yield self.http_client.fetch(
            self.get_url('/people/2'),
            method='DELETE',
            raise_error=False,
        )
        self.assertEqual(response.code, 200, 'DELETE endpoint did not return 200.')
        self.assertEqual(response.body, b'["Rick", "Maggie", "Carol", "Daryl"]\n', 'Unexpected body in response to DELETE.')

    @gen_test
    def test_api_error_endpoint(self):
        '''Error in a cell should cause 500 HTTP status
        '''
        response = yield self.http_client.fetch(
            self.get_url('/error'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 500, 'Cell with error did not return 500 status code.')

    @gen_test
    def test_api_unsupported_method(self):
        '''Endpoints which are not registered should return 404 HTTP status
        '''
        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='DELETE',
            raise_error=False
        )
        self.assertEqual(response.code, 404, 'Endpoint which exists, but does not support DELETE, did not return 405 status code.')

    @gen_test
    def test_api_unsupported_method(self):
        '''Endpoints which are registered, but do not support an HTTP method, should return a 405 HTTP status code
        '''
        response = yield self.http_client.fetch(
            self.get_url('/not/an/endpoint'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404, 'Endpoint which should not exist did not return 404 status code.')

    @gen_test
    def test_api_access_http_header(self):
        '''HTTP endpoints should be able to access request headers
        '''
        content_types = ['text/plain', 'application/json', 'application/atom+xml', 'foo']
        for content_type in content_types:
            response = yield self.http_client.fetch(
                self.get_url('/content-type'),
                method='GET',
                raise_error=False,
                headers={'Content-Type': content_type}
            )
            self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
            self.assertEqual(response.body.decode(encoding='UTF-8'), '{}\n'.format(content_type), 'Unexpected value in response')


class TestConcurrentAPIGatewayApp(TestGatewayAppBase):
    def setup_app(self):
        self.app.prespawn_count = 3
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_should_cycle_through_kernels(self):
        '''
        Requests should cycle through kernels
        '''
        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='PUT',
            body='hola {}',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'PUT endpoint did not return 200.')

        for i in range(self.app.prespawn_count):
            response = yield self.http_client.fetch(
                self.get_url('/message'),
                method='GET',
                raise_error=False
            )

            if i != self.app.prespawn_count-1:
                self.assertEqual(response.body, b'hello {}\n', 'Unexpected body in response to GET after performing PUT.')
            else:
                self.assertEqual(response.body, b'hola {}\n', 'Unexpected body in response to GET after performing PUT.')
    @gen_test
    def test_concurrent_request_should_not_be_blocked(self):
        '''
        Concurrent requests should not be blocked
        '''
        response_long_running = self.http_client.fetch(
            self.get_url('/sleep/6'),
            method='GET',
            raise_error=False
        )
        self.assertTrue(response_long_running.running(), 'Long HTTP Request is not running')
        response_short_running = yield self.http_client.fetch(
            self.get_url('/sleep/3'),
            method='GET',
            raise_error=False
        )
        self.assertTrue(response_long_running.running(), 'Long HTTP Request is not running')
        self.assertEqual(response_short_running.code, 200, 'Short HTTP Request did not return proper status code of 200')

    @gen_test
    def test_locking_semaphore_of_kernel_resources(self):
        '''
        Semaphore should properly control access to the kernel pool when all
        kernels are busy/requests overwhelm the kernel prespawn count
        '''
        futures = []
        for _ in range(self.app.prespawn_count*2+1):
            futures.append(self.http_client.fetch(
                self.get_url('/sleep/1'),
                method='GET',
                raise_error=False
            ))

        count = 0
        for future in futures:
            yield future
            count += 1
            if count >= self.app.prespawn_count + 1:
                break

class TestSwaggerSpecGeneration(TestGatewayAppBase):
    def setup_app(self):
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'simple_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_generation_of_swagger_spec(self):
        '''
        Notebook source should exists under the path /_api/source
        when allow_notebook download is True
        '''
        expected_response = {
            "info": {
                "version": "0.0.0",
                "title": "simple_api{}".format(sys.version_info.major)
            },
            "paths": {
                "/name": {
                    "get": {"responses": {"200": {"description": "Success"}}},
                    "post": {"responses": {"200": {"description": "Success"}}}
                }
            },
            "swagger": "2.0"
        }

        response = yield self.http_client.fetch(
            self.get_url('/_api/spec/swagger.json'),
            method='GET',
            raise_error=False
        )
        result = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 200, "Swagger spec endpoint did not return the correct status code")
        self.assertEqual(result, expected_response, "Swagger spec endpoint did not return the correct value")

class TestSettingResponse(TestGatewayAppBase):
    def setup_app(self):
        self.app.api = 'notebook-http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'responses_{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_setting_content_type(self):
        '''A response cell should allow the content type to be set'''
        response = yield self.http_client.fetch(
            self.get_url('/json'),
            method='GET',
            raise_error=False
        )
        result = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 200, 'Response status was not 200')
        self.assertEqual(response.headers['Content-Type'], 'application/json', 'Incorrect mime type was set on response')
        self.assertEqual(result, {'hello' : 'world'}, 'Incorrect response value.')

    @gen_test
    def test_setting_response_status_code(self):
        '''A response cell should allow the response status code to be set'''
        response = yield self.http_client.fetch(
            self.get_url('/nocontent'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 204, 'Response status was not 204')
        self.assertEqual(response.body, b'', 'Incorrect response value.')

    @gen_test
    def test_setting_etag_header(self):
        '''A response cell should allow the etag header to be set'''
        response = yield self.http_client.fetch(
            self.get_url('/etag'),
            method='GET',
            raise_error=False
        )
        result = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 200, 'Response status was not 200')
        self.assertEqual(response.headers['Content-Type'], 'application/json', 'Incorrect mime type was set on response')
        self.assertEqual(result, {'hello' : 'world'}, 'Incorrect response value.')
        self.assertEqual(response.headers['Etag'], '1234567890', 'Incorrect Etag header value.')
