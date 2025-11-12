# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for jupyter-enterprise-gateway."""

import os
import time
import uuid
from tempfile import TemporaryDirectory

from tornado.escape import json_decode, url_escape
from tornado.testing import gen_test

from .test_handlers import TestHandlers

pjoin = os.path.join


class TestEnterpriseGateway(TestHandlers):
    def setUp(self):
        super().setUp()
        # Enable debug logging if necessary
        # app = self.get_app()
        # app.settings['kernel_manager'].log.level = logging.DEBUG

    @gen_test
    def test_max_kernels_per_user(self):
        """
        Number of kernels should be limited per user.
        """

        self.get_app()
        self.app.max_kernels_per_user = 1

        # Request a kernel for bob
        bob_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body='{"env": {"KERNEL_USERNAME": "bob"} }'
        )
        self.assertEqual(bob_response.code, 201)

        # Request a kernel for alice
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
        )
        self.assertEqual(alice_response.code, 201)

        # Request another for alice - 403 expected
        failed_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False,
        )
        self.assertEqual(failed_response.code, 403)

        # Shut down the kernel for alice
        kernel = json_decode(alice_response.body)
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels/" + url_escape(kernel["id"])), method="DELETE"
        )
        self.assertEqual(response.code, 204)

        # Try again for alice - expect success
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
        )
        self.assertEqual(alice_response.code, 201)

    @gen_test
    def test_authorization(self):
        """
        Verify authorized users can start a kernel, unauthorized users cannot
        """

        self.get_app()
        self.app.authorized_users = {"bob", "alice", "bad_guy"}
        self.app.unauthorized_users = {"bad_guy"}

        # Request a kernel for alice
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
        )
        self.assertEqual(alice_response.code, 201)

        # Request a kernel for bad_guy - 403 expected
        failed_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "bad_guy"} }',
            raise_error=False,
        )
        self.assertEqual(failed_response.code, 403)

    @gen_test
    def test_port_range(self):
        """
        Verify port-range behaviors are correct
        """

        app = self.get_app()
        self.app.port_range = "10000..10999"  # range too small
        # Request a kernel for alice - 500 expected
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False,
        )
        self.assertEqual(alice_response.code, 500)

        self.app.port_range = "100..11099"  # invalid lower port
        # Request a kernel for alice - 500 expected
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False,
        )
        self.assertEqual(alice_response.code, 500)

        self.app.port_range = "10000..65537"  # invalid upper port
        # Request a kernel for alice - 500 expected
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False,
        )
        self.assertEqual(alice_response.code, 500)

        self.app.port_range = "30000..31000"  # valid range
        # Request a kernel for alice - 201 expected
        alice_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
        )
        self.assertEqual(alice_response.code, 201)

        # validate ports are in range
        body = json_decode(alice_response.body)
        kernel_id = body["id"]
        port_list = app.settings["kernel_manager"]._kernels.get(kernel_id).ports

        for port in port_list:
            self.assertTrue(30000 <= port <= 31000)

    @gen_test
    def test_dynamic_updates(self):
        app = self.app  # Get the actual EnterpriseGatewayApp instance
        s1 = time.time()
        name = app.config_file_name + ".py"
        with TemporaryDirectory("_1") as td1:
            os.environ["JUPYTER_CONFIG_DIR"] = td1
            config_file = pjoin(td1, name)
            with open(config_file, "w") as f:
                f.writelines(
                    [
                        "c.EnterpriseGatewayApp.impersonation_enabled = False\n",
                        "c.AsyncMappingKernelManager.cull_connected = False\n",
                    ]
                )
            #  app.jupyter_path.append(td1)
            app.load_config_file()
            app.add_dynamic_configurable("EnterpriseGatewayApp", app)
            app.add_dynamic_configurable("RemoteMappingKernelManager", app.kernel_manager)
            with self.assertRaises(RuntimeError):
                app.add_dynamic_configurable("Bogus", app.log)

            self.assertEqual(app.impersonation_enabled, False)
            self.assertEqual(app.kernel_manager.cull_connected, False)

            # Ensure file update doesn't happen during same second as initial value.
            # This is necessary on test systems that don't have finer-grained
            # timestamps (of less than a second).
            s2 = time.time()
            if s2 - s1 < 1.0:
                time.sleep(1.0 - (s2 - s1))
            # update config file
            with open(config_file, "w") as f:
                f.writelines(
                    [
                        "c.EnterpriseGatewayApp.impersonation_enabled = True\n",
                        "c.AsyncMappingKernelManager.cull_connected = True\n",
                    ]
                )

            # trigger reload and verify updates
            app.update_dynamic_configurables()
            self.assertEqual(app.impersonation_enabled, True)
            self.assertEqual(app.kernel_manager.cull_connected, True)

            # repeat to ensure no unexpected changes occurred
            app.update_dynamic_configurables()
            self.assertEqual(app.impersonation_enabled, True)
            self.assertEqual(app.kernel_manager.cull_connected, True)

    @gen_test
    def test_kernel_id_env_var(self):
        """
        Verify kernel is created with the given kernel id
        """
        expected_kernel_id = str(uuid.uuid4())
        kernel_response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body='{"env": {"KERNEL_ID": "%s"}}' % expected_kernel_id,
            raise_error=False,
        )
        self.assertEqual(kernel_response.code, 201)
        kernel = json_decode(kernel_response.body)
        self.assertEqual(expected_kernel_id, kernel["id"])
