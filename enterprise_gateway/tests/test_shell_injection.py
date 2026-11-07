# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for shell command injection in the kernel launch paths.

The DistributedProcessProxy builds the remote kernel startup command by
concatenating client-supplied KERNEL_* environment values into a shell string
that is executed on a remote host over SSH.  These tests assert that a value
containing POSIX shell metacharacters (command substitution, backticks,
variable expansion, quote-breakout) cannot influence the remote shell.

The bundled kernelspec launch scripts (etc/kernelspecs/*/bin/run.sh) run
``eval exec ...`` over strings that can contain client-supplied values
(GHSA-j63f-r6hc-x235).  These tests assert that such values are rejected when
they carry shell syntax, and that accepted values only become arguments.
"""

import asyncio
import json
import os
import shutil
import string
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from jupyter_client.ioloop.manager import AsyncIOLoopKernelManager
from jupyter_client.kernelspec import KernelSpec
from tornado import web

from enterprise_gateway.services.kernels.handlers import MainKernelHandler
from enterprise_gateway.services.kernels.remotemanager import RemoteKernelManager
from enterprise_gateway.services.processproxies.distributed import DistributedProcessProxy
from enterprise_gateway.services.processproxies.processproxy import (
    BaseProcessProxyABC,
    validate_eval_reaching_env,
)

KERNELSPECS_DIR = Path(__file__).resolve().parents[2] / "etc" / "kernelspecs"
BASH = shutil.which("bash")


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


class TestEvalReachingEnvValidation(unittest.TestCase):
    """Client values pasted into strings that launch scripts ``eval`` must not carry shell syntax."""

    # Bash operators, quoting and expansion characters, written out by hand.
    SHELL_SYNTAX_CHARS = (
        ";",
        "&",
        "|",
        "<",
        ">",
        "(",
        ")",
        "$",
        "`",
        "\\",
        '"',
        "'",
        "\n",
        "\r",
        "\x00",
    )

    def assert_rejected(self, client_env, kernelspec_env=None, extra_names=()):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_eval_reaching_env(client_env, kernelspec_env, extra_names)
        self.assertEqual(ctx.exception.status_code, 400)
        return ctx.exception

    def test_shell_syntax_rejected_in_extra_spark_opts(self):
        for char in self.SHELL_SYNTAX_CHARS:
            with self.subTest(char=repr(char)):
                self.assert_rejected({"KERNEL_EXTRA_SPARK_OPTS": f"--conf spark.a=b{char}c"})

    def test_word_starting_with_hash_rejected(self):
        """A word-initial '#' would comment out the rest of the eval'd line (e.g. --proxy-user)."""
        for value in ["#x", "--conf spark.a=b #x", "--conf spark.a=b\t#x"]:
            with self.subTest(value=value):
                self.assert_rejected({"KERNEL_EXTRA_SPARK_OPTS": value})

    def test_error_message_names_key_not_value(self):
        error = self.assert_rejected({"KERNEL_EXTRA_SPARK_OPTS": "s3cr3t;x"})
        self.assertIn("KERNEL_EXTRA_SPARK_OPTS", error.log_message)
        self.assertNotIn("s3cr3t", error.log_message)

    def test_realistic_values_accepted(self):
        values = [
            "",
            "--conf spark.executor.memory=2g --num-executors 4",
            "--master local[*]",
            "--archives env.tgz#environment",
            "--conf spark.driver.extraJavaOptions=-Dlog4j.configuration=file:/etc/log4j.properties",
            "--packages com.databricks:spark-xml_2.12:0.15.0,graphframes:graphframes:0.8.2",
        ]
        for value in values:
            with self.subTest(value=value):
                validate_eval_reaching_env({"KERNEL_EXTRA_SPARK_OPTS": value}, {})

    def test_bundled_paste_points_validated_without_kernelspec_reference(self):
        """Values EG's own scripts and process proxies paste into eval'd strings."""
        names = [
            "KERNEL_USERNAME",
            "KERNEL_EXTRA_SPARK_OPTS",
            "KERNEL_SPARK_OPTS",
            "KERNEL_SPARK_HOME",
            "KERNEL_PYSPARK_PYTHON",
            "KERNEL_NOTEBOOK_MASTER_REST",
            "KERNEL_CPUS",
            "KERNEL_MEMORY",
            "KERNEL_CPUS_LIMIT",
            "KERNEL_MEMORY_LIMIT",
            "KERNEL_SPARK_CONTEXT_INIT_MODE",
            "SPARK_HOME",
            "DASK_YARN_EXE",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assert_rejected({name: "a;b"}, kernelspec_env={})

    def test_variable_referenced_in_kernelspec_opts_validated(self):
        references = [
            ("SPARK_OPTS", "--name x ${KERNEL_MY_CONF}"),
            ("SPARK_OPTS", "--name x $KERNEL_MY_CONF"),
            ("SPARK_OPTS", "--name x ${KERNEL_MY_CONF:-default}"),
            ("__TOREE_SPARK_OPTS__", "--name x ${KERNEL_MY_CONF}"),
            ("LAUNCH_OPTS", "${KERNEL_MY_CONF}"),
        ]
        for key, template in references:
            with self.subTest(key=key, template=template):
                self.assert_rejected({"KERNEL_MY_CONF": "a;b"}, kernelspec_env={key: template})

    def test_variable_referenced_only_outside_opts_not_validated(self):
        """Non-*_OPTS kernelspec entries are not passed to eval, so quotes there stay legal."""
        validate_eval_reaching_env(
            {"KERNEL_MY_CONF": "it's fine"}, {"PYTHONPATH": "/opt/${KERNEL_MY_CONF}"}
        )

    def test_unrelated_structured_value_with_quotes_accepted(self):
        mounts = '[{"name": "data", "mountPath": "/data"}]'
        validate_eval_reaching_env({"KERNEL_VOLUME_MOUNTS": mounts}, {"SPARK_OPTS": "--name x"})

    def test_client_supplied_opts_variable_validated(self):
        for name in ["SPARK_OPTS", "LAUNCH_OPTS", "DASK_OPTS", "KERNEL_CUSTOM_OPTS"]:
            with self.subTest(name=name):
                self.assert_rejected({name: "a;b"}, kernelspec_env={})

    def test_operator_extra_names_validated(self):
        self.assert_rejected({"KERNEL_CUSTOM": "a;b"}, {}, extra_names=["KERNEL_CUSTOM"])

    def test_empty_extra_name_ignored(self):
        """Comma-split traits default to [''], which must not match anything."""
        validate_eval_reaching_env({"": "a;b"}, {}, extra_names=[""])


def _make_kernel_manager(kernelspec_env=None, proxy_config=None, inherited_envs=()):
    """Build a RemoteKernelManager with an in-memory kernelspec and no real launch."""
    km = RemoteKernelManager(kernel_name="test")
    metadata = {}
    if proxy_config is not None:
        metadata["process_proxy"] = {
            "class_name": "enterprise_gateway.services.processproxies.processproxy.LocalProcessProxy",
            "config": proxy_config,
        }
    km._kernel_spec = KernelSpec(
        argv=["/bin/true"],
        display_name="Test",
        language="python",
        env=kernelspec_env or {},
        metadata=metadata,
    )
    km.inherited_envs = list(inherited_envs)
    km.client_envs = []
    km.eval_validated_envs = []
    return km


class TestStartKernelValidatesEvalReachingEnv(unittest.TestCase):
    """RemoteKernelManager.start_kernel rejects bad values before any launch state exists."""

    def start(self, km, env):
        with patch.object(RemoteKernelManager, "_get_process_proxy") as get_proxy, patch.object(
            AsyncIOLoopKernelManager, "start_kernel", new=AsyncMock()
        ) as launch:
            try:
                asyncio.run(km.start_kernel(env=env))
            finally:
                self.get_proxy, self.launch = get_proxy, launch

    def test_rejected_value_creates_no_process_proxy_and_no_launch(self):
        km = _make_kernel_manager()
        with self.assertRaises(web.HTTPError) as ctx:
            self.start(km, {"KERNEL_EXTRA_SPARK_OPTS": "--conf a=b;c"})
        self.assertEqual(ctx.exception.status_code, 400)
        self.get_proxy.assert_not_called()
        self.launch.assert_not_awaited()

    def test_clean_value_launches(self):
        km = _make_kernel_manager()
        self.start(km, {"KERNEL_EXTRA_SPARK_OPTS": "--conf spark.executor.memory=2g"})
        self.launch.assert_awaited_once()

    def test_value_inherited_from_gateway_env_not_validated(self):
        """Operator-controlled values (exactly as inherited) are trusted."""
        km = _make_kernel_manager(inherited_envs=["OPS_EXTRA_OPTS"])
        with patch.dict(os.environ, {"OPS_EXTRA_OPTS": "a;b"}):
            self.start(km, {"OPS_EXTRA_OPTS": "a;b"})
        self.launch.assert_awaited_once()

    def test_client_override_of_inherited_name_validated(self):
        km = _make_kernel_manager(inherited_envs=["OPS_EXTRA_OPTS"])
        with patch.dict(os.environ, {"OPS_EXTRA_OPTS": "a"}), self.assertRaises(web.HTTPError):
            self.start(km, {"OPS_EXTRA_OPTS": "a;b"})
        self.launch.assert_not_awaited()

    def test_kernelspec_proxy_config_names_validated(self):
        km = _make_kernel_manager(proxy_config={"eval_validated_envs": "KERNEL_A,KERNEL_CUSTOM"})
        with self.assertRaises(web.HTTPError):
            self.start(km, {"KERNEL_CUSTOM": "a;b"})

    def test_operator_trait_names_validated(self):
        km = _make_kernel_manager()
        km.eval_validated_envs = ["KERNEL_CUSTOM"]
        with self.assertRaises(web.HTTPError):
            self.start(km, {"KERNEL_CUSTOM": "a;b"})

    def test_kernelspec_opts_reference_validated(self):
        km = _make_kernel_manager(kernelspec_env={"SPARK_OPTS": "--name x ${KERNEL_MY_CONF}"})
        with self.assertRaises(web.HTTPError):
            self.start(km, {"KERNEL_MY_CONF": "a;b"})


@unittest.skipIf(BASH is None, "bash is required to run the kernelspec launch scripts")
class TestEvalLaunchScriptSafety(unittest.TestCase):
    """Run the real yarn-cluster run.sh against a stub spark-submit.

    The script passes SPARK_OPTS and IMPERSONATION_OPTS through ``eval``.  Values the
    validator accepts must only add arguments: the impersonation flag, the launch
    script and the kernel arguments must survive, and nothing else may run.
    """

    KERNELSPEC = KERNELSPECS_DIR / "spark_python_yarn_cluster"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        spark_bin = self.tmp / "spark" / "bin"
        spark_bin.mkdir(parents=True)
        stub = spark_bin / "spark-submit"
        stub.write_text('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > "$ARGV_OUT"\n')
        stub.chmod(0o755)
        self.workdir = self.tmp / "work"
        self.workdir.mkdir()
        self.kernel_id = str(uuid.uuid4())
        self.spark_opts_template = json.loads((self.KERNELSPEC / "kernel.json").read_text())["env"][
            "SPARK_OPTS"
        ]

    def run_script(self, extra_spark_opts):
        """Launch run.sh the way EG does: Template-filled SPARK_OPTS, then the script's eval."""
        client_env = {"KERNEL_EXTRA_SPARK_OPTS": extra_spark_opts, "KERNEL_USERNAME": "alice"}
        argv_out = self.tmp / "argv.txt"
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.tmp),
            "SPARK_HOME": str(self.tmp / "spark"),
            "EG_IMPERSONATION_ENABLED": "True",
            "KERNEL_ID": self.kernel_id,
            "LAUNCH_OPTS": "",
            "ARGV_OUT": str(argv_out),
            # jupyter_client fills the kernelspec env from the request env before launch.
            "SPARK_OPTS": string.Template(self.spark_opts_template).safe_substitute(client_env),
            **client_env,
        }
        result = subprocess.run(
            [BASH, str(self.KERNELSPEC / "bin" / "run.sh"), "--kernel-id", self.kernel_id],
            cwd=self.workdir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return argv_out.read_text().splitlines()

    def assert_launch_tail_intact(self, argv):
        """Impersonation, launch script and kernel args must close the command line."""
        self.assertEqual(argv[-5:-3], ["--proxy-user", "alice"])
        self.assertTrue(argv[-3].endswith("/scripts/launch_ipykernel.py"), argv[-3])
        self.assertEqual(argv[-2:], ["--kernel-id", self.kernel_id])

    def test_accepted_values_only_add_arguments(self):
        values = [
            "--conf spark.executor.memory=2g --num-executors 4",
            "--archives env.tgz#environment",
            "--conf spark.a={x,y} --conf spark.b=~/x --conf spark.c=a!b",
            "--conf spark.d=* --conf spark.e=a%b^c+d@e,f:g",
            "",
        ]
        for value in values:
            with self.subTest(value=value):
                validate_eval_reaching_env({"KERNEL_EXTRA_SPARK_OPTS": value}, {})
                argv = self.run_script(value)
                self.assert_launch_tail_intact(argv)
                self.assertEqual(os.listdir(self.workdir), [], "the eval'd line created files")

    def test_client_options_reach_spark_submit_as_separate_arguments(self):
        argv = self.run_script("--conf spark.executor.memory=2g --num-executors 4")
        self.assertEqual(
            argv[-9:-5], ["--conf", "spark.executor.memory=2g", "--num-executors", "4"]
        )
        self.assertIn("--name", argv)
        self.assertEqual(argv[argv.index("--name") + 1], self.kernel_id)

    def test_word_starting_hash_would_drop_impersonation(self):
        """Why the validator rejects word-initial '#': eval treats it as a comment."""
        argv = self.run_script("--conf spark.a=b #x")
        self.assertNotIn("--proxy-user", argv)


if __name__ == "__main__":
    unittest.main()
