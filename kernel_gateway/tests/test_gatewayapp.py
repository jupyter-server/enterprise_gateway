# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for basic gateway app behavior."""

import logging
import unittest
import os
from kernel_gateway.gatewayapp import KernelGatewayApp, ioloop
from ..notebook_http.swagger.handlers import SwaggerSpecHandler
from tornado.testing import AsyncHTTPTestCase, LogTrapTestCase

RESOURCES = os.path.join(os.path.dirname(__file__), 'resources')

class TestGatewayAppConfig(unittest.TestCase):
    """Tests configuration of the gateway app."""
    def setUp(self):
        """Saves a copy of the environment."""
        self.environ = dict(os.environ)

    def tearDown(self):
        """Resets the environment."""
        os.environ = self.environ

    def test_config_env_vars(self):
        """Env vars should be honored for traitlets."""
        # Environment vars are always strings
        os.environ['KG_PORT'] = '1234'
        os.environ['KG_PORT_RETRIES'] = '4321'
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
        os.environ['KG_FORCE_KERNEL_NAME'] = 'fake_kernel_forced'
        os.environ['KG_DEFAULT_KERNEL_NAME'] = 'fake_kernel'
        os.environ['KG_KEYFILE'] = '/test/fake.key'
        os.environ['KG_CERTFILE'] = '/test/fake.crt'
        os.environ['KG_CLIENT_CA'] = '/test/fake_ca.crt'

        app = KernelGatewayApp()

        self.assertEqual(app.port, 1234)
        self.assertEqual(app.port_retries, 4321)
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
        self.assertEqual(app.force_kernel_name, 'fake_kernel_forced')
        self.assertEqual(app.keyfile, '/test/fake.key')
        self.assertEqual(app.certfile, '/test/fake.crt')
        self.assertEqual(app.client_ca, '/test/fake_ca.crt')

class TestGatewayAppBase(AsyncHTTPTestCase, LogTrapTestCase):
    """Base class for integration style tests using HTTP/Websockets against an
    instance of the gateway app.

    Attributes
    ----------
    app : KernelGatewayApp
        Instance of the app
    """
    def tearDown(self):
        """Shuts down the app after test run."""
        if self.app:
            self.app.shutdown()
        # Make sure the generated Swagger output is reset for subsequent tests
        SwaggerSpecHandler.output = None
        super(TestGatewayAppBase, self).tearDown()

    def get_new_ioloop(self):
        """Uses a global zmq ioloop for tests."""
        return ioloop.IOLoop.current()

    def get_app(self):
        """Returns a tornado.web.Application for the Tornado test runner."""
        if hasattr(self, '_app'):
            return self._app
        self.app = KernelGatewayApp(log_level=logging.CRITICAL)
        self.setup_app()
        self.app.init_configurables()
        self.setup_configurables()
        self.app.init_webapp()
        return self.app.web_app

    def setup_app(self):
        """Override to configure KernelGatewayApp instance before initializing
        configurables and the web app.
        """
        pass

    def setup_configurables(self):
        """Override to configure further settings, such as the personality.
        """
        pass
