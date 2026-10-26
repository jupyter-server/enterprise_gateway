# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for kernel prespawning."""

import asyncio
import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from jupyter_server.services.kernels.kernelmanager import AsyncMappingKernelManager
from tornado.testing import AsyncTestCase, gen_test

from enterprise_gateway.enterprisegatewayapp import EnterpriseGatewayApp
from enterprise_gateway.services.kernels.remotemanager import RemoteMappingKernelManager
from enterprise_gateway.services.processproxies.processproxy import BaseProcessProxyABC


class TestPrespawnKernels(AsyncTestCase):
    """Tests for RemoteMappingKernelManager.prespawn_kernels method."""

    def setUp(self):
        """Set up a kernel manager whose kernel launches are mocked."""
        super().setUp()
        self.manager = RemoteMappingKernelManager(parent=EnterpriseGatewayApp())
        self.manager.start_prespawned_kernel = AsyncMock(return_value="kernel-id")

    @gen_test(timeout=10)
    async def test_prespawn_kernels_zero_count(self):
        """Test prespawning with zero prespawn count."""
        await self.manager.prespawn_kernels(0)

        # Should complete successfully without spawning kernels
        self.assertTrue(self.manager.prespawn_complete.is_set())
        self.manager.start_prespawned_kernel.assert_not_called()

    @gen_test(timeout=10)
    async def test_prespawn_kernels_success(self):
        """Test successful prespawning."""
        await self.manager.prespawn_kernels(2)

        # Should complete successfully
        self.assertTrue(self.manager.prespawn_complete.is_set())
        self.assertEqual(self.manager.start_prespawned_kernel.await_count, 2)

    @gen_test(timeout=10)
    async def test_prespawn_kernels_partial_failure(self):
        """A kernel that keeps failing is retried twice, with backoff, while the others start."""
        spawn_error = Exception("Spawn failed")
        # Kernel 0 starts on its first attempt; kernel 1 fails its first attempt and both retries
        self.manager.start_prespawned_kernel.side_effect = [
            "kernel-1",
            spawn_error,
            spawn_error,
            spawn_error,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
            await self.manager.prespawn_kernels(2)

        self.assertTrue(self.manager.prespawn_complete.is_set())
        self.assertEqual(self.manager.start_prespawned_kernel.await_count, 4)
        self.assertEqual([call.args for call in sleep.await_args_list], [(1.0,), (2.0,)])

    @gen_test(timeout=10)
    async def test_prespawn_kernels_total_failure(self):
        """Test prespawning with total failure."""
        # Mock all failures
        self.manager.start_prespawned_kernel.side_effect = Exception("All spawns failed")

        with patch("asyncio.sleep", new_callable=AsyncMock), self.assertRaises(RuntimeError):
            await self.manager.prespawn_kernels(2)

        # Anything awaiting prespawning must not wait forever after it fails
        self.assertTrue(self.manager.prespawn_complete.is_set())

    @gen_test(timeout=10)
    async def test_prespawn_kernels_cancelled_spawns_are_failures(self):
        """A cancelled spawn started no kernel, so it must not be counted as a success."""
        self.manager.start_prespawned_kernel.side_effect = asyncio.CancelledError()

        with self.assertRaisesRegex(RuntimeError, "Failed to prespawn any kernels"):
            await self.manager.prespawn_kernels(2)


class TestRemoteManagerPrespawnedKernel(unittest.TestCase):
    """Tests for RemoteMappingKernelManager.start_prespawned_kernel method."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a minimal app and manager setup
        self.app = EnterpriseGatewayApp()
        self.app.runtime_dir = self.temp_dir
        self.app.default_kernel_name = "python3"

    def tearDown(self):
        """Clean up test fixtures."""
        # Launch tests leave a connection file behind in the runtime dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_start_prespawned_kernel_defaults(self):
        """Test that start_prespawned_kernel sets appropriate defaults."""
        manager = RemoteMappingKernelManager(parent=self.app)

        with patch.object(
            AsyncMappingKernelManager, "start_kernel", return_value="kernel-1"
        ) as mock_start:
            result = asyncio.run(manager.start_prespawned_kernel())

        self.assertEqual(result, "kernel-1")
        mock_start.assert_called_once()
        self.assertEqual(mock_start.call_args.kwargs["kernel_name"], "python3")
        self.assertEqual(mock_start.call_args.kwargs["env"]["KERNEL_USERNAME"], "prespawn")

    def test_start_prespawned_kernel_without_default_kernel_name(self):
        """Without a configured default_kernel_name, the kernel manager's default is used."""
        self.app.default_kernel_name = ""  # EG's default: not configured
        manager = RemoteMappingKernelManager(parent=self.app)

        with patch.object(
            AsyncMappingKernelManager, "start_kernel", return_value="kernel-1"
        ) as mock_start:
            asyncio.run(manager.start_prespawned_kernel())

        self.assertEqual(mock_start.call_args.kwargs["kernel_name"], "python3")

    def _launch_prespawned_kernel_until_popen(self):
        """Runs start_prespawned_kernel down the real launch path, stopping at subprocess.Popen.

        Popen is autospec'd, so arguments it doesn't accept fail just as they would for
        real.  Port selection is stubbed because it binds sockets.  Returns Popen's kwargs.
        """
        self.app.init_configurables()
        stop = RuntimeError("stop before spawning the kernel")
        with patch.object(
            BaseProcessProxyABC,
            "select_ports",
            lambda _self, count: list(range(52001, 52001 + count)),
        ), patch(
            "jupyter_client.launcher.Popen", autospec=True, side_effect=stop
        ) as popen, self.assertRaises(
            RuntimeError
        ) as raised:
            asyncio.run(self.app.kernel_manager.start_prespawned_kernel())
        self.assertIs(raised.exception, stop)
        return popen.call_args.kwargs

    def test_start_prespawned_kernel_reaches_popen(self):
        """Prespawn arguments must survive the real launch path down to subprocess.Popen."""
        popen_kwargs = self._launch_prespawned_kernel_until_popen()

        self.assertEqual(popen_kwargs["env"]["KERNEL_USERNAME"], "prespawn")

    def test_start_prespawned_kernel_env_has_only_inherited_envs(self):
        """Like kernel requests, prespawned kernels inherit only the configured inherited_envs."""
        self.app.inherited_envs = ["EG_TEST_INHERITED"]
        with patch.dict(os.environ, {"EG_TEST_INHERITED": "yes", "EG_TEST_NOT_INHERITED": "no"}):
            popen_kwargs = self._launch_prespawned_kernel_until_popen()

        self.assertEqual(popen_kwargs["env"]["EG_TEST_INHERITED"], "yes")
        self.assertNotIn("EG_TEST_NOT_INHERITED", popen_kwargs["env"])


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(level=logging.INFO)

    # Run the tests
    unittest.main()
