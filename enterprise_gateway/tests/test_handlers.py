# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for jupyter-websocket mode."""

import json
import os

from tornado.escape import json_decode, json_encode, url_escape
from tornado.gen import Return, coroutine
from tornado.httpclient import HTTPRequest
from tornado.testing import gen_test
from tornado.websocket import websocket_connect

from .test_gatewayapp import RESOURCES, TestGatewayAppBase


class TestHandlers(TestGatewayAppBase):
    """
    Base class for jupyter-websocket mode tests that spawn kernels.
    """

    def setup_app(self):
        """Configure JUPYTER_PATH so that we can use local kernelspec files for testing."""
        os.environ["JUPYTER_PATH"] = RESOURCES

        # These are required for setup of test_kernel_defaults
        # Note: We still reference the DEPRECATED config parameter and environment variable so that
        # we can test client_envs and inherited_envs, respectively.
        self.app.env_whitelist = ["TEST_VAR", "OTHER_VAR1", "OTHER_VAR2"]
        os.environ["EG_ENV_PROCESS_WHITELIST"] = "PROCESS_VAR1,PROCESS_VAR2"
        os.environ["PROCESS_VAR1"] = "process_var1_override"

    def tearDown(self):
        """Shuts down the app after test run."""

        # Clean out items added to env
        if "JUPYTER_PATH" in os.environ:
            os.environ.pop("JUPYTER_PATH")
        if "EG_ENV_PROCESS_WHITELIST" in os.environ:
            os.environ.pop("EG_ENV_PROCESS_WHITELIST")
        if "PROCESS_VAR1" in os.environ:
            os.environ.pop("PROCESS_VAR1")

        super().tearDown()

    @coroutine
    def spawn_kernel(self, kernel_body="{}"):
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
            self.get_url("/api/kernels"), method="POST", body=kernel_body
        )
        self.assertEqual(response.code, 201)

        # Connect to the kernel via websocket
        kernel = json_decode(response.body)
        ws_url = "ws://localhost:{}/api/kernels/{}/channels".format(
            self.get_http_port(), url_escape(kernel["id"])
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
            "header": {
                "username": "",
                "version": "5.0",
                "session": "",
                "msg_id": "fake-msg-id",
                "msg_type": "execute_request",
            },
            "parent_header": {},
            "channel": "shell",
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
            },
            "metadata": {},
            "buffers": {},
        }

    @coroutine
    def await_stream(self, ws):
        """Returns stream output associated with an execute_request."""
        while 1:
            msg = yield ws.read_message()
            msg = json_decode(msg)
            msg_type = msg["msg_type"]
            parent_msg_id = msg["parent_header"]["msg_id"]
            if msg_type == "stream" and parent_msg_id == "fake-msg-id":
                raise Return(msg["content"])


class TestDefaults(TestHandlers):
    """Tests gateway behavior."""

    @gen_test
    def test_startup(self):
        """Root of kernels resource should be OK."""
        self.app.web_app.settings["eg_list_kernels"] = True
        response = yield self.http_client.fetch(self.get_url("/api/kernels"))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_headless(self):
        """Other notebook resources should not exist."""
        response = yield self.http_client.fetch(self.get_url("/api/contents"), raise_error=False)
        self.assertEqual(response.code, 404)
        response = yield self.http_client.fetch(self.get_url("/"), raise_error=False)
        self.assertEqual(response.code, 404)
        response = yield self.http_client.fetch(self.get_url("/tree"), raise_error=False)
        self.assertEqual(response.code, 404)

    @gen_test
    def test_check_origin(self):
        """Allow origin setting should pass through to base handlers."""
        response = yield self.http_client.fetch(
            self.get_url("/api/kernelspecs"),
            method="GET",
            headers={"Origin": "fake.com:8888"},
            raise_error=False,
        )
        self.assertEqual(response.code, 404)

        app = self.get_app()
        app.settings["allow_origin"] = "*"

        response = yield self.http_client.fetch(
            self.get_url("/api/kernelspecs"),
            method="GET",
            headers={"Origin": "fake.com:8888"},
            raise_error=False,
        )
        self.assertEqual(response.code, 200)

    @gen_test
    def test_auth_token(self):
        """All server endpoints should check the configured auth token."""
        # Set token requirement
        app = self.get_app()
        app.settings["eg_auth_token"] = "fake-token"

        # Requst API without the token
        response = yield self.http_client.fetch(
            self.get_url("/api"), method="GET", raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Now with it
        response = yield self.http_client.fetch(
            self.get_url("/api"),
            method="GET",
            headers={"Authorization": "token fake-token"},
            raise_error=False,
        )
        self.assertEqual(response.code, 200)

        # Request kernelspecs without the token
        response = yield self.http_client.fetch(
            self.get_url("/api/kernelspecs"), method="GET", raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Now with it
        response = yield self.http_client.fetch(
            self.get_url("/api/kernelspecs"),
            method="GET",
            headers={"Authorization": "token fake-token"},
            raise_error=False,
        )
        self.assertEqual(response.code, 200)

        # Request a kernel without the token
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body="{}", raise_error=False
        )
        self.assertEqual(response.code, 401)

        # Request with the token now
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
            method="POST",
            body="{}",
            headers={"Authorization": "token fake-token"},
            raise_error=False,
        )
        self.assertEqual(response.code, 201)

        kernel = json_decode(response.body)
        # Request kernel info without the token
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels/" + url_escape(kernel["id"])),
            method="GET",
            raise_error=False,
        )
        self.assertEqual(response.code, 401)

        # Now with it
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels/" + url_escape(kernel["id"])),
            method="GET",
            headers={"Authorization": "token fake-token"},
            raise_error=False,
        )
        self.assertEqual(response.code, 200)

        # Request websocket connection without the token
        ws_url = "ws://localhost:{}/api/kernels/{}/channels".format(
            self.get_http_port(), url_escape(kernel["id"])
        )
        # No option to ignore errors so try/except
        try:
            ws = yield websocket_connect(ws_url)
        except Exception as ex:
            self.assertEqual(ex.code, 401)
        else:
            self.assertTrue(False, "no exception raised")

        # Now request the websocket with the token
        ws_req = HTTPRequest(ws_url, headers={"Authorization": "token fake-token"})
        ws = yield websocket_connect(ws_req)
        ws.close()

    @gen_test
    def test_cors_headers(self):
        """All kernel endpoints should respond with configured CORS headers."""
        app = self.get_app()
        app.settings["eg_allow_credentials"] = "false"
        app.settings["eg_allow_headers"] = "Authorization,Content-Type"
        app.settings["eg_allow_methods"] = "GET,POST"
        app.settings["eg_allow_origin"] = "https://jupyter.org"
        app.settings["eg_expose_headers"] = "X-My-Fake-Header"
        app.settings["eg_max_age"] = "600"
        app.settings["eg_list_kernels"] = True

        # Get kernels to check headers
        response = yield self.http_client.fetch(self.get_url("/api/kernels"), method="GET")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Credentials"], "false")
        self.assertEqual(
            response.headers["Access-Control-Allow-Headers"], "Authorization,Content-Type"
        )
        self.assertEqual(response.headers["Access-Control-Allow-Methods"], "GET,POST")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://jupyter.org")
        self.assertEqual(response.headers["Access-Control-Expose-Headers"], "X-My-Fake-Header")
        self.assertEqual(response.headers["Access-Control-Max-Age"], "600")
        self.assertEqual(response.headers.get("Content-Security-Policy"), None)

    @gen_test
    def test_max_kernels(self):
        """Number of kernels should be limited."""
        app = self.get_app()
        app.settings["eg_max_kernels"] = 1

        # Request a kernel
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body="{}"
        )
        self.assertEqual(response.code, 201)

        # Request another
        response2 = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body="{}", raise_error=False
        )
        self.assertEqual(response2.code, 403)

        # Shut down the kernel
        kernel = json_decode(response.body)
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels/" + url_escape(kernel["id"])), method="DELETE"
        )
        self.assertEqual(response.code, 204)

        # Try again
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body="{}"
        )
        self.assertEqual(response.code, 201)

    @gen_test
    def test_get_api(self):
        """Server should respond with the API version metadata."""
        response = yield self.http_client.fetch(self.get_url("/api"))
        self.assertEqual(response.code, 200)
        info = json_decode(response.body)
        self.assertIn("version", info)
        self.assertIn("gateway_version", info)

    @gen_test
    def test_get_kernelspecs(self):
        """Server should respond with kernel spec metadata."""
        response = yield self.http_client.fetch(self.get_url("/api/kernelspecs"))
        self.assertEqual(response.code, 200)
        specs = json_decode(response.body)
        self.assertIn("kernelspecs", specs)
        self.assertIn("default", specs)

    @gen_test
    def test_get_kernels(self):
        """Server should respond with running kernel information."""
        self.app.web_app.settings["eg_list_kernels"] = True
        response = yield self.http_client.fetch(self.get_url("/api/kernels"))
        self.assertEqual(response.code, 200)
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 0)

        # Launch a kernel
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body="{}"
        )
        self.assertEqual(response.code, 201)
        kernel = json_decode(response.body)

        # Check the list again
        response = yield self.http_client.fetch(self.get_url("/api/kernels"))
        self.assertEqual(response.code, 200)
        kernels = json_decode(response.body)
        self.assertEqual(len(kernels), 1)
        self.assertEqual(kernels[0]["id"], kernel["id"])

    @gen_test
    def test_kernel_comm(self):
        """Default kernel should launch and accept commands."""
        ws = yield self.spawn_kernel()

        # Send a request for kernel info
        ws.write_message(
            json_encode(
                {
                    "header": {
                        "username": "",
                        "version": "5.0",
                        "session": "",
                        "msg_id": "fake-msg-id",
                        "msg_type": "kernel_info_request",
                    },
                    "parent_header": {},
                    "channel": "shell",
                    "content": {},
                    "metadata": {},
                    "buffers": {},
                }
            )
        )

        # Assert the reply comes back. Test will timeout if this hangs.
        # Note that this range may be side-effected by upstream changes,
        # so we will add a print (and increase its length to 8).
        for _ in range(8):
            msg = yield ws.read_message()
            msg = json_decode(msg)
            if msg["msg_type"] == "kernel_info_reply":
                break
        else:
            self.assertTrue(False, "never received kernel_info_reply")
        ws.close()

    @gen_test
    def test_no_discovery(self):
        """The list of kernels / sessions should be forbidden by default."""
        response = yield self.http_client.fetch(self.get_url("/api/kernels"), raise_error=False)
        self.assertEqual(response.code, 403)

        response = yield self.http_client.fetch(self.get_url("/api/sessions"), raise_error=False)
        self.assertEqual(response.code, 403)

    @gen_test
    def test_crud_sessions(self):
        """Server should create, list, and delete sessions."""
        app = self.get_app()
        app.settings["eg_list_kernels"] = True

        # Ensure no sessions by default
        response = yield self.http_client.fetch(self.get_url("/api/sessions"))
        self.assertEqual(response.code, 200)
        sessions = json_decode(response.body)
        self.assertEqual(len(sessions), 0)

        # Launch a session
        response = yield self.http_client.fetch(
            self.get_url("/api/sessions"),
            method="POST",
            body='{"id":"any","notebook":{"path":"anywhere"},"kernel":{"name":"python"}}',
        )
        self.assertEqual(response.code, 201)
        session = json_decode(response.body)

        # Check the list again
        response = yield self.http_client.fetch(self.get_url("/api/sessions"))
        self.assertEqual(response.code, 200)
        sessions = json_decode(response.body)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["id"], session["id"])

        # Delete the session
        response = yield self.http_client.fetch(
            self.get_url("/api/sessions/" + session["id"]), method="DELETE"
        )
        self.assertEqual(response.code, 204)

        # Make sure the list is empty
        response = yield self.http_client.fetch(self.get_url("/api/sessions"))
        self.assertEqual(response.code, 200)
        sessions = json_decode(response.body)
        self.assertEqual(len(sessions), 0)

    @gen_test
    def test_json_errors(self):
        """Handlers should always return JSON errors."""
        # A handler that we override
        response = yield self.http_client.fetch(self.get_url("/api/kernels"), raise_error=False)
        body = json_decode(response.body)
        self.assertEqual(response.code, 403)
        self.assertEqual(body["reason"], "Forbidden")

        # A handler from the notebook base
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels/1-2-3-4-5"), raise_error=False
        )
        body = json_decode(response.body)
        self.assertEqual(response.code, 404)
        # Base handler json_errors decorator does not capture reason properly
        # self.assertEqual(body['reason'], 'Not Found')
        self.assertIn("1-2-3-4-5", body["message"])

        # The last resort not found handler
        response = yield self.http_client.fetch(self.get_url("/fake-endpoint"), raise_error=False)
        body = json_decode(response.body)
        self.assertEqual(response.code, 404)
        self.assertEqual(body["reason"], "Not Found")

    @gen_test
    def test_kernel_env(self):
        """Kernel should start with environment vars defined in the request."""
        # Note: Only envs in request prefixed with KERNEL_ or in env_whitelist (TEST_VAR)
        # with the exception of KERNEL_GATEWAY - which is "system owned".
        kernel_body = json.dumps(
            {
                "name": "python",
                "env": {
                    "KERNEL_FOO": "kernel-foo-value",
                    "NOT_KERNEL": "ignored",
                    "KERNEL_GATEWAY": "overridden",
                    "TEST_VAR": "allowed",
                },
            }
        )
        ws = yield self.spawn_kernel(kernel_body)
        req = self.execute_request(
            "import os; "
            'print(os.getenv("KERNEL_FOO"), '
            'os.getenv("NOT_KERNEL"), '
            'os.getenv("KERNEL_GATEWAY"), '
            'os.getenv("TEST_VAR"))'
        )
        ws.write_message(json_encode(req))
        content = yield self.await_stream(ws)
        self.assertEqual(content["name"], "stdout")
        self.assertIn("kernel-foo-value", content["text"])
        self.assertNotIn("ignored", content["text"])
        self.assertNotIn("overridden", content["text"])
        self.assertIn("allowed", content["text"])

        ws.close()

    @gen_test
    def test_kernel_defaults(self):
        """Kernel should start with env vars defined in request overriding env vars defined in kernelspec."""

        # Note: Only envs in request prefixed with KERNEL_ or in env_whitelist (OTHER_VAR1, OTHER_VAR2)
        # with the exception of KERNEL_GATEWAY - which is "system owned" - will be set in kernel env.
        # Since OTHER_VAR1 is not in the request, its existing value in kernel.json will be used.

        # NOTE: This test requires use of the kernels/kernel_defaults_test/kernel.json file.
        kernel_body = json.dumps(
            {
                "name": "kernel_defaults_test",
                "env": {
                    "KERNEL_VAR1": "kernel_var1_override",  # Ensure this value overrides that in kernel.json
                    "KERNEL_VAR3": "kernel_var3_value",  # Any KERNEL_ flows to kernel
                    "OTHER_VAR2": "other_var2_override",  # Ensure this value overrides that in kernel.json
                    "KERNEL_GATEWAY": "kernel_gateway_override",  # Ensure KERNEL_GATEWAY is not overridden
                },
            }
        )
        ws = yield self.spawn_kernel(kernel_body)
        req = self.execute_request(
            'import os; print(os.getenv("KERNEL_VAR1"), os.getenv("KERNEL_VAR2"), '
            'os.getenv("KERNEL_VAR3"), os.getenv("KERNEL_GATEWAY"), os.getenv("OTHER_VAR1"), '
            'os.getenv("OTHER_VAR2"), os.getenv("PROCESS_VAR1"), os.getenv("PROCESS_VAR2"))'
        )
        ws.write_message(json_encode(req))
        content = yield self.await_stream(ws)
        self.assertEqual(content["name"], "stdout")
        self.assertIn("kernel_var1_override", content["text"])
        self.assertIn("kernel_var2_default", content["text"])
        self.assertIn("kernel_var3_value", content["text"])
        self.assertNotIn("kernel_gateway_override", content["text"])
        self.assertIn("other_var1_default", content["text"])
        self.assertIn("other_var2_override", content["text"])
        self.assertIn("process_var1_override", content["text"])
        self.assertIn("process_var2_default", content["text"])
        ws.close()

    @gen_test
    def test_get_swagger_yaml_spec(self):
        """Getting the swagger.yaml spec should be ok"""
        response = yield self.http_client.fetch(self.get_url("/api/swagger.yaml"))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_get_swagger_json_spec(self):
        """Getting the swagger.json spec should be ok"""
        response = yield self.http_client.fetch(self.get_url("/api/swagger.json"))
        self.assertEqual(response.code, 200)

    @gen_test
    def test_kernel_env_auth_token(self):
        """Kernel should not have EG_AUTH_TOKEN in its environment."""
        os.environ["EG_AUTH_TOKEN"] = "fake-secret"
        ws = None
        try:
            ws = yield self.spawn_kernel()
            req = self.execute_request('import os; print(os.getenv("EG_AUTH_TOKEN"))')
            ws.write_message(json_encode(req))
            content = yield self.await_stream(ws)
            self.assertNotIn("fake-secret", content["text"])
        finally:
            del os.environ["EG_AUTH_TOKEN"]
            if ws:
                ws.close()


class TestCustomDefaultKernel(TestHandlers):
    """Tests gateway behavior when setting a custom default kernelspec."""

    def setup_app(self):
        self.app.default_kernel_name = "fake-kernel"

    @gen_test
    def test_default_kernel_name(self):
        """The default kernel name should be used on empty requests."""
        # Request without an explicit kernel name
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="POST", body="", raise_error=False
        )
        self.assertEqual(response.code, 500)
        self.assertTrue("raise NoSuchKernel" in str(response.body))


class TestEnableDiscovery(TestHandlers):
    """Tests gateway behavior with kernel listing enabled."""

    def setup_configurables(self):
        """Enables kernel listing for all tests."""
        self.app.list_kernels = True

    @gen_test
    def test_enable_kernel_list(self):
        """The list of kernels, sessions, and activities should be available."""
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"),
        )
        self.assertEqual(response.code, 200)
        self.assertTrue("[]" in str(response.body))
        response = yield self.http_client.fetch(
            self.get_url("/api/sessions"),
        )
        self.assertEqual(response.code, 200)
        self.assertTrue("[]" in str(response.body))


class TestBaseURL(TestHandlers):
    """Tests gateway behavior when a custom base URL is configured."""

    def setup_app(self):
        """Sets the custom base URL and enables kernel listing."""
        self.app.base_url = "/fake/path"

    def setup_configurables(self):
        """Enables kernel listing for all tests."""
        self.app.list_kernels = True

    @gen_test
    def test_base_url(self):
        """Server should mount resources under configured base."""
        # Should not exist at root
        response = yield self.http_client.fetch(
            self.get_url("/api/kernels"), method="GET", raise_error=False
        )
        self.assertEqual(response.code, 404)

        # Should exist under path
        response = yield self.http_client.fetch(
            self.get_url("/fake/path/api/kernels"), method="GET"
        )
        self.assertEqual(response.code, 200)


class TestRelativeBaseURL(TestHandlers):
    """Tests gateway behavior when a relative base URL is configured."""

    def setup_app(self):
        """Sets the custom base URL as a relative path."""
        self.app.base_url = "fake/path"

    @gen_test
    def test_base_url(self):
        """Server should mount resources under fixed base."""
        self.app.web_app.settings["eg_list_kernels"] = True

        # Should exist under path
        response = yield self.http_client.fetch(
            self.get_url("/fake/path/api/kernels"), method="GET"
        )
        self.assertEqual(response.code, 200)


class TestWildcardEnvs(TestHandlers):
    """Base class for jupyter-websocket mode tests that spawn kernels."""

    def setup_app(self):
        """Configure JUPYTER_PATH so that we can use local kernelspec files for testing."""
        super().setup_app()
        # overwrite env_whitelist
        self.app.env_whitelist = ["*"]

    @gen_test
    def test_kernel_wildcard_env(self):
        """Kernel should start with environment vars defined in the request."""
        # Note: Since env_whitelist == '*', all values should be present.
        kernel_body = json.dumps(
            {
                "name": "python",
                "env": {
                    "KERNEL_FOO": "kernel-foo-value",
                    "OTHER_VAR1": "other-var1-value",
                    "OTHER_VAR2": "other-var2-value",
                    "TEST_VAR": "test-var-value",
                },
            }
        )
        ws = yield self.spawn_kernel(kernel_body)
        req = self.execute_request(
            "import os; "
            'print(os.getenv("KERNEL_FOO"), '
            'os.getenv("OTHER_VAR1"), '
            'os.getenv("OTHER_VAR2"), '
            'os.getenv("TEST_VAR"))'
        )
        ws.write_message(json_encode(req))
        content = yield self.await_stream(ws)
        self.assertEqual(content["name"], "stdout")
        self.assertIn("kernel-foo-value", content["text"])
        self.assertIn("other-var1-value", content["text"])
        self.assertIn("other-var2-value", content["text"])
        self.assertIn("test-var-value", content["text"])

        ws.close()
