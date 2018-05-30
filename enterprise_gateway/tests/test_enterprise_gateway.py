# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for jupyter-enterprise-gateway."""

import logging
from tornado.testing import gen_test
from tornado.escape import json_decode, url_escape
from .test_jupyter_websocket import TestJupyterWebsocket


class TestEnterpriseGateway(TestJupyterWebsocket):

    def setUp(self):
        super(TestJupyterWebsocket, self).setUp()
        # Enable debug logging if necessary
        #app = self.get_app()
        #app.settings['kernel_manager'].log.level = logging.DEBUG

    @gen_test
    def test_max_kernels_per_user(self):
        """Number of kernels should be limited per user."""

        app = self.get_app()
        app.settings['kernel_manager'].parent.max_kernels_per_user = 1

        # Request a kernel for bob
        bob_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "bob"} }'
        )
        self.assertEqual(bob_response.code, 201)

        # Request a kernel for alice
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }'
        )
        self.assertEqual(alice_response.code, 201)

        # Request another for alice - 403 expected
        failed_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False
        )
        self.assertEqual(failed_response.code, 403)

        # Shut down the kernel for alice
        kernel = json_decode(alice_response.body)
        response = yield self.http_client.fetch(
            self.get_url('/api/kernels/' + url_escape(kernel['id'])),
            method='DELETE'
        )
        self.assertEqual(response.code, 204)

        # Try again for alice - expect success
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }'
        )
        self.assertEqual(alice_response.code, 201)

    @gen_test
    def test_authorization(self):
        """Verify authorized users can start a kernel, unauthorized users cannot"""

        app = self.get_app()
        app.settings['kernel_manager'].parent.authorized_users = {'bob', 'alice', 'bad_guy'}
        app.settings['kernel_manager'].parent.unauthorized_users = {'bad_guy'}

        # Request a kernel for alice
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }'
        )
        self.assertEqual(alice_response.code, 201)

        # Request a kernel for bad_guy - 403 expected
        failed_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "bad_guy"} }',
            raise_error=False
        )
        self.assertEqual(failed_response.code, 403)

    @gen_test
    def test_port_range(self):
        """Verify port-range behaviors are correct"""

        app = self.get_app()
        app.settings['kernel_manager'].parent.port_range = "10000..10999"  # range too small
        # Request a kernel for alice - 500 expected
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False
        )
        self.assertEqual(alice_response.code, 500)

        app.settings['kernel_manager'].parent.port_range = "100..11099"  # invalid lower port
        # Request a kernel for alice - 500 expected
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False
        )
        self.assertEqual(alice_response.code, 500)

        app.settings['kernel_manager'].parent.port_range = "10000..65537"  # invalid upper port
        # Request a kernel for alice - 500 expected
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }',
            raise_error=False
        )
        self.assertEqual(alice_response.code, 500)

        app.settings['kernel_manager'].parent.port_range = "30000..31000"  # valid range
        # Request a kernel for alice - 201 expected
        alice_response = yield self.http_client.fetch(
            self.get_url('/api/kernels'),
            method='POST',
            body='{"env": {"KERNEL_USERNAME": "alice"} }'
        )
        self.assertEqual(alice_response.code, 201)

        # validate ports are in range
        body = json_decode(alice_response.body)
        kernel_id = body['id']
        port_list = app.settings['kernel_manager']._kernels.get(kernel_id).ports

        for port in port_list:
            self.assertTrue(30000 <= port <= 31000)
