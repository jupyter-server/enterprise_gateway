# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for basic gateway app behavior."""

import logging
import os
import unittest

from tornado.testing import AsyncHTTPTestCase, ExpectLog

from enterprise_gateway.enterprisegatewayapp import EnterpriseGatewayApp
from enterprise_gateway.mixins import EnterpriseGatewayConfigMixin

RESOURCES = os.path.join(os.path.dirname(__file__), "resources")


class TestGatewayAppConfig(unittest.TestCase):
    """Tests configuration of the gateway app."""

    def setUp(self):
        """Saves a copy of the environment."""
        self.environ = dict(os.environ)

    def tearDown(self):
        """Resets the environment."""
        os.environ.clear()
        os.environ.update(self.environ)

    def _assert_envs_to_traitlets(self, env_prefix: str):
        app = EnterpriseGatewayApp()
        app.init_configurables()

        self.assertEqual(app.port, 1234)
        self.assertEqual(app.port_retries, 4321)
        self.assertEqual(app.ip, "1.1.1.1")
        self.assertEqual(app.auth_token, "fake-token")
        self.assertEqual(app.allow_credentials, "true")
        self.assertEqual(app.allow_headers, "Authorization")
        self.assertEqual(app.allow_methods, "GET")
        self.assertEqual(app.allow_origin, "*")
        self.assertEqual(app.expose_headers, "X-Fake-Header")
        self.assertEqual(app.max_age, "5")
        self.assertEqual(app.base_url, "/fake/path")
        self.assertEqual(app.max_kernels, 1)
        self.assertEqual(app.default_kernel_name, "fake_kernel")
        self.assertEqual(app.keyfile, "/test/fake.key")
        self.assertEqual(app.certfile, "/test/fake.crt")
        self.assertEqual(app.client_ca, "/test/fake_ca.crt")
        self.assertEqual(app.ssl_version, 3)
        if env_prefix == "EG_":  # These options did not exist in JKG
            self.assertEqual(app.kernel_session_manager.enable_persistence, True)
            self.assertEqual(
                app.availability_mode, EnterpriseGatewayConfigMixin.AVAILABILITY_REPLICATION
            )

    def test_config_env_vars_bc(self):
        """B/C env vars should be honored for traitlets."""
        # Environment vars are always strings
        os.environ["KG_PORT"] = "1234"
        os.environ["KG_PORT_RETRIES"] = "4321"
        os.environ["KG_IP"] = "1.1.1.1"
        os.environ["KG_AUTH_TOKEN"] = "fake-token"
        os.environ["KG_ALLOW_CREDENTIALS"] = "true"
        os.environ["KG_ALLOW_HEADERS"] = "Authorization"
        os.environ["KG_ALLOW_METHODS"] = "GET"
        os.environ["KG_ALLOW_ORIGIN"] = "*"
        os.environ["KG_EXPOSE_HEADERS"] = "X-Fake-Header"
        os.environ["KG_MAX_AGE"] = "5"
        os.environ["KG_BASE_URL"] = "/fake/path"
        os.environ["KG_MAX_KERNELS"] = "1"
        os.environ["KG_DEFAULT_KERNEL_NAME"] = "fake_kernel"
        os.environ["KG_KEYFILE"] = "/test/fake.key"
        os.environ["KG_CERTFILE"] = "/test/fake.crt"
        os.environ["KG_CLIENT_CA"] = "/test/fake_ca.crt"
        os.environ["KG_SSL_VERSION"] = "3"

        self._assert_envs_to_traitlets("KG_")

    def test_config_env_vars(self):
        """Env vars should be honored for traitlets."""
        # Environment vars are always strings
        os.environ["EG_PORT"] = "1234"
        os.environ["EG_PORT_RETRIES"] = "4321"
        os.environ["EG_IP"] = "1.1.1.1"
        os.environ["EG_AUTH_TOKEN"] = "fake-token"
        os.environ["EG_ALLOW_CREDENTIALS"] = "true"
        os.environ["EG_ALLOW_HEADERS"] = "Authorization"
        os.environ["EG_ALLOW_METHODS"] = "GET"
        os.environ["EG_ALLOW_ORIGIN"] = "*"
        os.environ["EG_EXPOSE_HEADERS"] = "X-Fake-Header"
        os.environ["EG_MAX_AGE"] = "5"
        os.environ["EG_BASE_URL"] = "/fake/path"
        os.environ["EG_MAX_KERNELS"] = "1"
        os.environ["EG_DEFAULT_KERNEL_NAME"] = "fake_kernel"
        os.environ["EG_KEYFILE"] = "/test/fake.key"
        os.environ["EG_CERTFILE"] = "/test/fake.crt"
        os.environ["EG_CLIENT_CA"] = "/test/fake_ca.crt"
        os.environ["EG_SSL_VERSION"] = "3"
        os.environ["EG_KERNEL_SESSION_PERSISTENCE"] = (
            "True"  # availability mode will be defaulted to replication
        )

        self._assert_envs_to_traitlets("EG_")

    def test_ssl_options_no_config(self):
        app = EnterpriseGatewayApp()
        ssl_options = app._build_ssl_options()
        self.assertIsNone(ssl_options)


class TestGatewayAppBase(AsyncHTTPTestCase, ExpectLog):
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

        super().tearDown()

    def get_app(self):
        """Returns a tornado.web.Application for the Tornado test runner."""
        if hasattr(self, "_app"):
            return self._app
        self.app = EnterpriseGatewayApp(log_level=logging.CRITICAL)
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
        """Override to configure further settings, such as the personality."""
        pass
