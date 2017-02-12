# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for jupyter-websocket mode."""

import os
import sys
import json

from .test_gatewayapp import TestGatewayAppBase, RESOURCES

from kernel_gateway.gatewayapp import KernelGatewayApp
from jupyter_client.kernelspec import NoSuchKernel

from tornado.gen import coroutine, Return, sleep
from tornado.websocket import websocket_connect
from tornado.httpclient import HTTPRequest
from tornado.testing import gen_test
from tornado.escape import json_encode, json_decode, url_escape


class TestJupyterWebsocket(TestGatewayAppBase):
    """Base class for jupyter-websocket mode tests that spawn kernels."""
    @coroutine
    def spawn_kernel(self, kernel_body='{}'):
        """Spawns a kernel using the gateway API and connects a websocket
        client to it.

        Parameters
        ----------
        kernel_body : str
            POST /api/kernels body

        Returns
        -------
        Future
            Promise of a WebSocketClientConnection
        """
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

    def execute_request(self, code):
        """Creates an execute_request message.

        Parameters
        ----------
        code : str
            Code to execute

        Returns
        -------
        dict
            The message
        """
        return {
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
        }

    @coroutine
    def await_stream(self, ws):
        """Returns stream output associated with an execute_request."""
        while 1:
            msg = yield ws.read_message()
            msg = json_decode(msg)
            msg_type = msg['msg_type']
            parent_msg_id = msg['parent_header']['msg_id']
            if msg_type == 'stream' and parent_msg_id == 'fake-msg-id':
                raise Return(msg['content'])


class TestDefaults(TestJupyterWebsocket):
    """Tests gateway behavior."""
    @gen_test
    def test_startup(self):
        """Root of kernels resource should be OK."""
        self.app.web_app.settings['kg_list_kernels'] = True
        response = yield self.http_client.fetch(self.get_url('/api/kernels'))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_headless(self):
        """Other notebook resources should not exist."""
        response = yield self.http_client.fetch(self.get_url('/api/contents'),
            raise_error=False)
        self.assertEqual(response.code, 404)
        response = yield self.http_client.fetch(self.get_url('/'),
            raise_error=False)
        self.assertEqual(response.code, 404)
        response = yield self.http_client.fetch(self.get_url('/tree'),
            raise_error=False)
        self.assertEqual(response.code, 404)

    @gen_test
    def test_check_origin(self):
        """Allow origin setting should pass through to base handlers."""
        response = yield self.http_client.fetch(
            self.get_url('/api/kernelspecs'),
            method='GET',
            headers={'Origin': 'fake.com:8888'},
            raise_error=False
        )
        self.assertEqual(response.code, 404)

        app = self.get_app()
        app.settings['allow_origin'] = '*'

        response = yield self.http_client.fetch(
            self.get_url('/api/kernelspecs'),
            method='GET',
            headers={'Origin': 'fake.com:8888'},
            raise_error=False
        )
        self.assertEqual(response.code, 200)

    @gen_test
    def test_config_bad_api_value(self):
        """Should raise an ImportError for nonexistent API personality modules."""
        def _set_api():
            self.app.api = 'notebook-gopher'
        self.assertRaises(ImportError, _set_api)

    @gen_test
    def test_auth_token(self):
        """All server endpoints should check the configured auth token."""
        # Set token requirement
        app = self.get_app()
        app.settings['kg_auth_token'] = 'fake-token'

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

        # Request kernelspecs without the token
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
        """All kernel endpoints should respond with configured CORS headers."""
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
        """Number of kernels should be limited."""
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
        self.assertEqual(response2.code, 403)

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
        """Server should respond with the API version metadata."""
        response = yield self.http_client.fetch(
            self.get_url('/api')
        )
        self.assertEqual(response.code, 200)
        info = json_decode(response.body)
        self.assertIn('version', info)

    @gen_test
    def test_get_kernelspecs(self):
        """Server should respond with kernel spec metadata."""
        response = yield self.http_client.fetch(
            self.get_url('/api/kernelspecs')
        )
        self.assertEqual(response.code, 200)
        specs = json_decode(response.body)
        self.assertIn('kernelspecs', specs)
        self.assertIn('default', specs)

    @gen_test
    def test_get_kernels(self):
        """Server should respond with running kernel information."""
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
        """Default kernel should launch and accept commands."""
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
    def test_no_discovery(self):
        """The list of kernels / sessions should be forbidden by default."""
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            raise_error=False
        )
        self.assertEqual(response.code, 403)

        response = yield self.http_client.fetch(
            self.get_url('/api/sessions'),
            raise_error=False
        )
        self.assertEqual(response.code, 403)

        response = yield self.http_client.fetch(
            self.get_url('/_api/activity'),
            raise_error=False
        )
        self.assertEqual(response.code, 403)

    @gen_test
    def test_crud_sessions(self):
        """Server should create, list, and delete sessions."""
        app = self.get_app()
        app.settings['kg_list_kernels'] = True

        # Ensure no sessions by default
        response = yield self.http_client.fetch(
            self.get_url('/api/sessions')
        )
        self.assertEqual(response.code, 200)
        sessions = json_decode(response.body)
        self.assertEqual(len(sessions), 0)

        # Launch a session
        response = yield self.http_client.fetch(
            self.get_url('/api/sessions'),
            method='POST',
            body='{"id":"any","notebook":{"path":"anywhere"},"kernel":{"name":"python"}}'
        )
        self.assertEqual(response.code, 201)
        session = json_decode(response.body)

        # Check the list again
        response = yield self.http_client.fetch(
            self.get_url('/api/sessions')
        )
        self.assertEqual(response.code, 200)
        sessions = json_decode(response.body)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['id'], session['id'])

        # Delete the session
        response = yield self.http_client.fetch(
            self.get_url('/api/sessions/'+session['id']),
            method='DELETE'
        )
        self.assertEqual(response.code, 204)

        # Make sure the list is empty
        response = yield self.http_client.fetch(
            self.get_url('/api/sessions')
        )
        self.assertEqual(response.code, 200)
        sessions = json_decode(response.body)
        self.assertEqual(len(sessions), 0)

    @gen_test
    def test_json_errors(self):
        """Handlers should always return JSON errors."""
        # A handler that we override
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            raise_error=False
        )
        body = json_decode(response.body)
        self.assertEqual(response.code, 403)
        self.assertEqual(body['reason'], 'Forbidden')

        # A handler from the notebook base
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels/1-2-3-4-5'),
            raise_error=False
        )
        body = json_decode(response.body)
        self.assertEqual(response.code, 404)
        # Base handler json_errors decorator does not capture reason properly
        # self.assertEqual(body['reason'], 'Not Found')
        self.assertIn('1-2-3-4-5', body['message'])

        # The last resort not found handler
        response = yield self.http_client.fetch(
            self.get_url('/fake-endpoint'),
            raise_error=False
        )
        body = json_decode(response.body)
        self.assertEqual(response.code, 404)
        self.assertEqual(body['reason'], 'Not Found')

    @gen_test
    def test_kernel_env(self):
        """Kernel should start with environment vars defined in the request."""
        self.app.personality.env_whitelist = ['TEST_VAR']
        kernel_body = json.dumps({
            'name': 'python',
            'env': {
                'KERNEL_FOO': 'kernel-foo-value',
                'NOT_KERNEL': 'ignored',
                'KERNEL_GATEWAY': 'overridden',
                'TEST_VAR': 'allowed'
            }
        })
        ws = yield self.spawn_kernel(kernel_body)
        req = self.execute_request('import os; print(os.getenv("KERNEL_FOO"), os.getenv("NOT_KERNEL"), os.getenv("KERNEL_GATEWAY"), os.getenv("TEST_VAR"))')
        ws.write_message(json_encode(req))
        content = yield self.await_stream(ws)
        self.assertEqual(content['name'], 'stdout')
        self.assertIn('kernel-foo-value', content['text'])
        self.assertNotIn('ignored', content['text'])
        self.assertNotIn('overridden', content['text'])
        self.assertIn('allowed', content['text'])

        ws.close()

    @gen_test
    def test_get_swagger_yaml_spec(self):
        """Getting the swagger.yaml spec should be ok"""
        response = yield self.http_client.fetch(self.get_url('/api/swagger.yaml'))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_get_swagger_json_spec(self):
        """Getting the swagger.json spec should be ok"""
        response = yield self.http_client.fetch(self.get_url('/api/swagger.json'))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_kernel_env_auth_token(self):
        """Kernel should not have KG_AUTH_TOKEN in its environment."""
        os.environ['KG_AUTH_TOKEN'] = 'fake-secret'

        try:
            ws = yield self.spawn_kernel()
            req = self.execute_request('import os; print(os.getenv("KG_AUTH_TOKEN"))')
            ws.write_message(json_encode(req))
            content = yield self.await_stream(ws)
            self.assertNotIn('fake-secret', content['text'])
        finally:
            del os.environ['KG_AUTH_TOKEN']
            ws.close()


class TestCustomDefaultKernel(TestJupyterWebsocket):
    """Tests gateway behavior when setting a custom default kernelspec."""
    def setup_app(self):
        self.app.default_kernel_name = 'fake-kernel'

    @gen_test
    def test_default_kernel_name(self):
        """The default kernel name should be used on empty requests."""
        # Request without an explicit kernel name
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='',
            raise_error=False
        )
        self.assertEqual(response.code, 500)
        self.assertTrue('raise NoSuchKernel' in str(response.body))


class TestForceKernel(TestJupyterWebsocket):
    """Tests gateway behavior when forcing a kernelspec."""
    def setup_app(self):
        self.app.prespawn_count = 2
        self.app.seed_uri = os.path.join(RESOURCES,
            'zen{}.ipynb'.format(sys.version_info.major))
        self.app.force_kernel_name = 'python{}'.format(sys.version_info.major)

    @gen_test
    def test_force_kernel_name(self):
        """Should create a Python kernel."""
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"name": "fake-kernel"}',
            raise_error=False
        )
        self.assertEqual(response.code, 201)


class TestEnableDiscovery(TestJupyterWebsocket):
    """Tests gateway behavior with kernel listing enabled."""
    def setup_configurables(self):
        """Enables kernel listing for all tests."""
        self.app.personality.list_kernels = True

    @gen_test
    def test_enable_kernel_list(self):
        """The list of kernels, sessions, and activities should be available."""
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
        )
        self.assertEqual(response.code, 200)
        self.assertTrue('[]' in str(response.body))
        response = yield self.http_client.fetch(
            self.get_url('/api/sessions'),
        )
        self.assertEqual(response.code, 200)
        self.assertTrue('[]' in str(response.body))
        response = yield self.http_client.fetch(
            self.get_url('/_api/activity'),
        )
        self.assertEqual(response.code, 200)
        self.assertTrue('{}' in str(response.body))


class TestPrespawnKernels(TestJupyterWebsocket):
    """Tests gateway behavior when kernels are spawned at startup."""
    def setup_app(self):
        """Always prespawn 2 kernels."""
        self.app.prespawn_count = 2

    @gen_test(timeout=10)
    def test_prespawn_count(self):
        """Server should launch the given number of kernels on startup."""
        self.app.web_app.settings['kg_list_kernels'] = True
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels')
        )
        self.assertEqual(response.code, 200)
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 2)

    def test_prespawn_max_conflict(self):
        """Server should error if prespawn count is greater than max allowed
        kernels.
        """
        app = KernelGatewayApp()
        app.prespawn_count = 3
        app.max_kernels = 2
        self.assertRaises(RuntimeError, app.init_configurables)


class TestBaseURL(TestJupyterWebsocket):
    """Tests gateway behavior when a custom base URL is configured."""
    def setup_app(self):
        """Sets the custom base URL and enables kernel listing."""
        self.app.base_url = '/fake/path'

    def setup_configurables(self):
        """Enables kernel listing for all tests."""
        self.app.personality.list_kernels = True

    @gen_test
    def test_base_url(self):
        """Server should mount resources under configured base."""
        # Should not exist at root
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404)
        response = yield self.http_client.fetch(
            self.get_url('/_api/activity'),
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

        response = yield self.http_client.fetch(
            self.get_url('/fake/path/_api/activity'),
            method='GET'
        )
        self.assertEqual(response.code, 200)


class TestRelativeBaseURL(TestJupyterWebsocket):
    """Tests gateway behavior when a relative base URL is configured."""
    def setup_app(self):
        """Sets the custom base URL as a relative path."""
        self.app.base_url = 'fake/path'

    @gen_test
    def test_base_url(self):
        """Server should mount resources under fixed base."""
        self.app.web_app.settings['kg_list_kernels'] = True

        # Should exist under path
        response = yield self.http_client.fetch(
            self.get_url('/fake/path/api/kernels'),
            method='GET'
        )
        self.assertEqual(response.code, 200)


class TestSeedURI(TestJupyterWebsocket):
    """Tests gateway behavior when a seeding kernel memory with code from a
    notebook."""
    def setup_app(self):
        self.app.seed_uri = os.path.join(RESOURCES,
            'zen{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_seed(self):
        """Kernel should have variables preseeded from the notebook."""
        ws = yield self.spawn_kernel()

        # Print the encoded "zen of python" string, the kernel should have
        # it imported
        req = self.execute_request('print(this.s)')
        ws.write_message(json_encode(req))
        content = yield self.await_stream(ws)
        self.assertEqual(content['name'], 'stdout')
        self.assertIn('Gur Mra bs Clguba', content['text'])

        ws.close()


class TestRemoteSeedURI(TestSeedURI):
    """Tests gateway behavior when a seeding kernel memory with code from a
    remote notebook.
    """
    def setup_app(self):
        """Sets the seed notebook to a remote notebook."""
        self.app.seed_uri = 'https://gist.githubusercontent.com/parente/ccd36bd7db2f617d58ce/raw/zen{}.ipynb'.format(sys.version_info.major)


class TestBadSeedURI(TestJupyterWebsocket):
    """Tests gateway behavior when seeding kernel memory with notebook code
    that fails.
    """
    def setup_app(self):
        """Sets the seed notebook to one of the test resources."""
        self.app.seed_uri = os.path.join(RESOURCES,
            'failing_code{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_seed_error(self):
        """
        Server should shutdown kernel and respond with error when seed notebook
        has an execution error.
        """
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
        """
        Server should error because seed notebook requires a kernel that is not
        installed.
        """
        app = KernelGatewayApp()
        app.seed_uri = os.path.join(RESOURCES, 'unknown_kernel.ipynb')
        self.assertRaises(NoSuchKernel, app.init_configurables)


class TestKernelLanguageSupport(TestJupyterWebsocket):
    """Tests gateway behavior when a client requests a specific kernel spec."""
    def setup_app(self):
        """Sets the app to prespawn one kernel and preseed it with one of the
        test notebooks.
        """
        self.app.prespawn_count = 1
        self.app.seed_uri = os.path.join(RESOURCES,
            'zen{}.ipynb'.format(sys.version_info.major))

    @coroutine
    def spawn_kernel(self):
        """Override the base class spawn utility method to set the Python kernel
        version number when spawning.
        """
        kernel_body = json.dumps({"name":"python{}".format(sys.version_info.major)})
        ws = yield super(TestKernelLanguageSupport, self).spawn_kernel(kernel_body)
        raise Return(ws)

    @gen_test
    def test_seed_language_support(self):
        """Kernel should have variables preseeded from notebook."""
        ws = yield self.spawn_kernel()

        if sys.version_info.major == 2:
            code = 'print this.s'
        else:
            code = 'print(this.s)'

        # Print the encoded "zen of python" string, the kernel should have
        # it imported
        req = self.execute_request(code)
        ws.write_message(json_encode(req))
        content = yield self.await_stream(ws)
        self.assertEqual(content['name'], 'stdout')
        self.assertIn('Gur Mra bs Clguba', content['text'])

        ws.close()


class TestActivityAPI(TestJupyterWebsocket):
    """Tests gateway behavior when the activity API is enabled."""
    def setup_configurables(self):
        """Enables kernel listing so the activity API is available."""
        self.app.personality.list_kernels = True

    @gen_test(timeout=10)
    def test_api_lists_kernels_with_flag_set(self):
        """Server should report initial activity values for one kernel with
        one client connected to it.
        """
        ws = yield self.spawn_kernel()
        req = self.execute_request('import time\ntime.sleep(1)')
        ws.write_message(json_encode(req))

        # Get the first set of activities
        response = yield self.http_client.fetch(
            self.get_url('/_api/activity'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200)
        first_kernel_id, first_activity_data = json.loads(response.body.decode('UTF-8')).popitem()
        # Close the websocket and get the activities
        ws.close()

        # Give the socket time to disconnect
        yield sleep(3)

        # Request the activity
        response = yield self.http_client.fetch(
            self.get_url('/_api/activity'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200)
        second_kernel_id, second_activity_data = json.loads(response.body.decode('UTF-8')).popitem()

        self.assertEqual(first_kernel_id, second_kernel_id, 'Kernel IDs were not equal')
        self.assertEqual(first_activity_data['connections'], 1, 'The wrong number of connections existed during the first request')
        self.assertEqual(second_activity_data['connections'], 0, 'The wrong number of connections existed during the second request')
