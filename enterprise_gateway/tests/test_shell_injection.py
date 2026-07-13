# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for shell command injection in the SSH/distributed kernel launch path.

The DistributedProcessProxy builds the remote kernel startup command by
concatenating client-supplied KERNEL_* environment values into a shell string
that is executed on a remote host over SSH.  These tests assert that a value
containing POSIX shell metacharacters (command substitution, backticks,
variable expansion, quote-breakout) cannot influence the remote shell.
"""

import os
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from tornado import web

from enterprise_gateway.services.kernels.handlers import MainKernelHandler
from enterprise_gateway.services.processproxies.distributed import DistributedProcessProxy
from enterprise_gateway.services.processproxies.processproxy import BaseProcessProxyABC


def _make_proxy(kernel_spec_env=None):
    """Build a DistributedProcessProxy bypassing the heavy __init__.

    _build_startup_command only depends on ``self.ip`` and
    ``self.kernel_manager.kernel_spec.env``, so we set just those.
    """
    proxy = DistributedProcessProxy.__new__(DistributedProcessProxy)
    proxy.ip = "203.0.113.5"  # non-local (TEST-NET-3); branch forced below anyway
    proxy.log = Mock()
    proxy.kernel_manager = Mock()
    proxy.kernel_manager.kernel_spec.env = kernel_spec_env or {}
    return proxy


def _exports_only(cmd: str) -> str:
    """Return just the ``export ...;`` prefix, before the nohup/argv tail."""
    return cmd.split("nohup", 1)[0]


class TestDistributedStartupCommandInjection(unittest.TestCase):
    """The remote export statements must not execute embedded shell code."""

    def setUp(self):
        # Force the remote (non-local) branch deterministically.
        patcher = patch.object(BaseProcessProxyABC, "ip_is_local", return_value=False)
        self.addCleanup(patcher.stop)
        patcher.start()
        self._tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self._tmpdir, ignore_errors=True))

    def _run_exports(self, cmd: str) -> None:
        """Execute the export prefix in a POSIX shell (no kernel argv)."""
        subprocess.run(
            ["/bin/sh", "-c", _exports_only(cmd) + " true"],
            check=True,
        )

    def test_command_substitution_does_not_execute(self):
        proxy = _make_proxy()
        marker = os.path.join(self._tmpdir, "pwned_dollar")
        env = {"KERNEL_ID": "abc", "KERNEL_FOO": f"x$(touch {marker})"}

        cmd = proxy._build_startup_command(["python"], env=env)
        self._run_exports(cmd)

        self.assertFalse(
            os.path.exists(marker),
            "Command substitution $(...) in a KERNEL_ value executed on the shell",
        )

    def test_backtick_substitution_does_not_execute(self):
        proxy = _make_proxy()
        marker = os.path.join(self._tmpdir, "pwned_backtick")
        env = {"KERNEL_ID": "abc", "KERNEL_FOO": f"x`touch {marker}`"}

        cmd = proxy._build_startup_command(["python"], env=env)
        self._run_exports(cmd)

        self.assertFalse(
            os.path.exists(marker),
            "Backtick substitution in a KERNEL_ value executed on the shell",
        )

    def test_kernelspec_env_substitution_does_not_execute(self):
        marker = os.path.join(self._tmpdir, "pwned_spec")
        proxy = _make_proxy(kernel_spec_env={"SPEC_FOO": f"x$(touch {marker})"})
        env = {"KERNEL_ID": "abc"}

        cmd = proxy._build_startup_command(["python"], env=env)
        self._run_exports(cmd)

        self.assertFalse(
            os.path.exists(marker),
            "Command substitution in a kernelspec env value executed on the shell",
        )

    def test_normal_value_round_trips_intact(self):
        """Legitimate values (spaces, special chars) must survive quoting."""
        proxy = _make_proxy()
        value = "/home/jovyan/my data & stuff"
        env = {"KERNEL_ID": "abc", "KERNEL_FOO": value}

        cmd = proxy._build_startup_command(["python"], env=env)
        result = subprocess.run(
            ["/bin/sh", "-c", _exports_only(cmd) + ' printf %s "$KERNEL_FOO"'],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout, value)


def _make_handler(client_envs=None, inherited_envs=None):
    """Build a MainKernelHandler bypassing Tornado's request init.

    ``_build_kernel_env`` only reads ``self.client_envs`` / ``self.inherited_envs``,
    which are properties backed by ``self.settings``.
    """
    handler = MainKernelHandler.__new__(MainKernelHandler)
    handler.application = Mock()
    handler.application.settings = {
        "eg_client_envs": client_envs if client_envs is not None else [],
        "eg_inherited_envs": inherited_envs if inherited_envs is not None else [],
    }
    return handler


class TestKernelEnvBoundaryValidation(unittest.TestCase):
    """Defense-in-depth: reject shell-dangerous KERNEL_* values at the API boundary."""

    def test_command_substitution_rejected(self):
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_FOO": "x$(touch /tmp/pwned)"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_variable_expansion_rejected(self):
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_FOO": "${HOME}"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_backtick_rejected(self):
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_FOO": "x`id`"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_newline_rejected(self):
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_FOO": "line1\nline2"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_carriage_return_rejected(self):
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_FOO": "line1\rline2"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_null_byte_rejected(self):
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_FOO": "a\x00b"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_validation_applies_to_client_allowed_envs(self):
        """Non-KERNEL_ but client-allowed envs are validated too."""
        handler = _make_handler(client_envs=["MY_VAR"])
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"MY_VAR": "x$(id)"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_error_message_names_key_not_value(self):
        """Rejection must not echo the (possibly secret) value into the response."""
        handler = _make_handler()
        with self.assertRaises(web.HTTPError) as ctx:
            handler._build_kernel_env({"KERNEL_SECRET": "s3cr3t$(id)"})
        self.assertIn("KERNEL_SECRET", ctx.exception.log_message)
        self.assertNotIn("s3cr3t", ctx.exception.log_message)

    def test_legitimate_json_volume_mounts_allowed(self):
        handler = _make_handler()
        env = handler._build_kernel_env(
            {"KERNEL_VOLUME_MOUNTS": '[{"name": "data", "mountPath": "/data"}]'}
        )
        self.assertEqual(env["KERNEL_VOLUME_MOUNTS"], '[{"name": "data", "mountPath": "/data"}]')

    def test_legitimate_path_with_spaces_allowed(self):
        handler = _make_handler()
        env = handler._build_kernel_env({"KERNEL_WORKING_DIR": "/home/jovyan/my data"})
        self.assertEqual(env["KERNEL_WORKING_DIR"], "/home/jovyan/my data")

    def test_legitimate_display_name_allowed(self):
        handler = _make_handler()
        env = handler._build_kernel_env({"KERNEL_FOO": "Python 3 (ipykernel) - v1.2.3"})
        self.assertEqual(env["KERNEL_FOO"], "Python 3 (ipykernel) - v1.2.3")


if __name__ == "__main__":
    unittest.main()
