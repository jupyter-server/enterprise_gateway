"""Code used for the generic distribution of kernels across a set of hosts."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from __future__ import annotations

import asyncio
import os
import shlex
import signal
from collections.abc import Iterable
from socket import gethostbyname
from subprocess import STDOUT
from typing import Any, ClassVar

from tornado import web

from ..kernels.remotemanager import RemoteKernelManager
from .processproxy import BaseProcessProxyABC, RemoteProcessProxy

poll_interval = float(os.getenv("EG_POLL_INTERVAL", "0.5"))
kernel_log_dir = os.getenv(
    "EG_KERNEL_LOG_DIR", "/tmp"  # noqa
)  # would prefer /var/log, but its only writable by root


def _quote_kernelspec_env_value(value: str) -> str:
    """Quote an operator-authored kernelspec env value for the remote shell.

    Kernelspec env values may reference variables that the remote host is expected to
    resolve, such as ``${HOME}/.local`` or ``${KERNEL_ID:-...}``.  The value is therefore
    double-quoted so parameter expansion still happens, while command substitution
    (``$(...)``, backticks), arithmetic expansion (``$((...))``, ``$[...]``) and quote
    breakout are escaped and stay literal.

    Client-supplied values must not use this function: they are quoted with
    ``shlex.quote`` so nothing in them expands.  Arithmetic contexts inside a parameter
    expansion (e.g. ``${HOME:$OFFSET}``) are still evaluated, so kernelspec authors
    should not reference client variables there.

    Parameters
    ----------
    value : str
        The kernelspec env value, before template substitution.

    Returns
    -------
    str
        A double-quoted shell word.
    """
    escaped = (
        value.replace("\\", "\\\\")  # first, so the escapes added below stay intact
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$(", "\\$(")  # also covers $((
        .replace("$[", "\\$[")
    )
    return f'"{escaped}"'


def validate_remote_host(remote_host: str, allowed_hosts: Iterable[str]) -> str:
    """Return the configured remote host that a client's ``KERNEL_REMOTE_HOST`` names.

    Clients may pin a kernel to a host, but only to one of the kernel's configured remote
    hosts (``EG_REMOTE_HOSTS`` or the kernelspec's ``remote_hosts``).  Otherwise a client
    could make the gateway open SSH sessions, with its credentials, to any host.  Names
    are compared ignoring case, surrounding whitespace and a trailing dot.

    Parameters
    ----------
    remote_host : str
        The host requested through ``KERNEL_REMOTE_HOST``.
    allowed_hosts : Iterable[str]
        The kernel's configured remote hosts.

    Returns
    -------
    str
        The matching entry, exactly as configured.

    Raises
    ------
    tornado.web.HTTPError
        400 if ``remote_host`` is not one of ``allowed_hosts``.  The message does not
        echo the requested value.
    """
    requested = _normalize_host(remote_host)
    for host in allowed_hosts:
        if _normalize_host(host) == requested:
            return host
    raise web.HTTPError(
        400,
        "KERNEL_REMOTE_HOST is not one of this kernel's remote hosts. Add the host to "
        "EG_REMOTE_HOSTS or to the kernelspec's remote_hosts.",
    )


def _normalize_host(host: str) -> str:
    return host.strip().rstrip(".").lower()


class TrackKernelOnHost:
    """A class for tracking a kernel on a host."""

    _host_kernels: ClassVar = {}
    _kernel_host_mapping: ClassVar = {}

    def add_kernel_id(self, host: str, kernel_id: str) -> None:
        """Add a kernel to a host."""
        self._kernel_host_mapping[kernel_id] = host
        self.increment(host)

    def delete_kernel_id(self, kernel_id: str) -> None:
        """Delete a kernel id from tracking."""
        host = self._kernel_host_mapping.get(kernel_id)
        if host:
            self.decrement(host)
            del self._kernel_host_mapping[kernel_id]

    def min_or_remote_host(self, remote_host: str | None = None) -> str:
        """Return the remote host if given, or the kernel with the min value."""
        if remote_host:
            return remote_host
        return min(self._host_kernels, key=lambda k: self._host_kernels[k])

    def increment(self, host: str) -> None:
        """Increment the value for a host."""
        val = int(self._host_kernels.get(host, 0))
        self._host_kernels[host] = val + 1

    def decrement(self, host: str) -> None:
        """Decrement the value for a host."""
        val = int(self._host_kernels.get(host, 0))
        self._host_kernels[host] = val - 1

    def init_host_kernels(self, hosts) -> None:
        """Inititialize the kernels for a set of hosts."""
        if len(self._host_kernels) == 0:
            self._host_kernels.update({key: 0 for key in hosts})


class DistributedProcessProxy(RemoteProcessProxy):
    """
    Manages the lifecycle of kernels distributed across a set of hosts.
    """

    host_index = 0
    kernel_on_host = TrackKernelOnHost()

    def __init__(self, kernel_manager: RemoteKernelManager, proxy_config: dict):
        """Initialize the proxy."""
        super().__init__(kernel_manager, proxy_config)
        self.kernel_log = None
        self.local_stdout = None
        self.least_connection = kernel_manager.load_balancing_algorithm == "least-connection"
        if proxy_config.get("remote_hosts"):
            self.hosts = proxy_config.get("remote_hosts").split(",")
        else:
            self.hosts = kernel_manager.remote_hosts  # from command line or env

        if self.least_connection:
            DistributedProcessProxy.kernel_on_host.init_host_kernels(self.hosts)

    async def launch_process(
        self, kernel_cmd: str, **kwargs: dict[str, Any] | None
    ) -> DistributedProcessProxy:
        """
        Launches a kernel process on a selected host.
        """
        env_dict = kwargs.get("env")
        await super().launch_process(kernel_cmd, **kwargs)

        self.assigned_host = self._determine_next_host(env_dict)
        self.ip = gethostbyname(self.assigned_host)  # convert to ip if host is provided
        self.assigned_ip = self.ip

        try:
            result_pid = self._launch_remote_process(kernel_cmd, **kwargs)
            self.pid = int(result_pid)
        except Exception as e:
            error_message = "Failure occurred starting kernel on '{}'.  Returned result: {}".format(
                self.ip, e
            )
            self.log_and_raise(http_status_code=500, reason=error_message)

        self.log.info(
            "Kernel launched on '{}', pid: {}, ID: {}, Log file: {}:{}, Command: '{}'.  ".format(
                self.assigned_host,
                self.pid,
                self.kernel_id,
                self.assigned_host,
                self.kernel_log,
                kernel_cmd,
            )
        )
        await self.confirm_remote_startup()
        return self

    def _launch_remote_process(self, kernel_cmd: str, **kwargs: dict[str, Any] | None) -> str:
        """
        Launch the kernel as indicated by the argv stanza in the kernelspec.  Note that this method
        will bypass use of ssh if the remote host is also the local machine.
        """

        cmd = self._build_startup_command(kernel_cmd, **kwargs)
        self.log.debug(f"Invoking cmd: '{cmd}' on host: {self.assigned_host}")
        result_pid = "bad_pid"  # purposely initialize to bad int value

        if BaseProcessProxyABC.ip_is_local(self.ip):
            # launch the local command with redirection in place
            self.local_stdout = open(self.kernel_log, mode="a")  # noqa
            self.local_proc = self.launch_kernel(
                cmd, stdout=self.local_stdout, stderr=STDOUT, **kwargs
            )
            result_pid = str(self.local_proc.pid)
        else:
            # launch remote command via ssh
            result = self.rsh(self.ip, cmd)
            for line in result:
                result_pid = line.strip()

        return result_pid

    def _build_startup_command(self, argv_cmd: str, **kwargs: dict[str, Any] | None) -> str:
        """
        Builds the command to invoke by concatenating envs from kernelspec followed by the kernel argvs.

        We also force nohup, redirection to a file and place in background, then follow with an echo
        for the background pid.

        Note: We optimize for the local case and just return the existing command.
        """

        # Optimized case needs to also redirect the kernel output, so unconditionally compose kernel_log
        env_dict = kwargs["env"]
        kid = env_dict.get("KERNEL_ID")
        self.kernel_log = os.path.join(kernel_log_dir, f"kernel-{kid}.log")

        if BaseProcessProxyABC.ip_is_local(self.ip):  # We're local so just use what we're given
            cmd = argv_cmd
        else:  # Add additional envs, including those in kernelspec
            cmd = ""

            # Client-supplied values are fully quoted so nothing in them expands.
            for key, value in env_dict.items():
                cmd += f"export {shlex.quote(str(key))}={shlex.quote(str(value))};"

            # Kernelspec values come from the operator and may reference the remote
            # environment, so parameter expansion is preserved for them.
            for key, value in self.kernel_manager.kernel_spec.env.items():
                cmd += f"export {shlex.quote(str(key))}={_quote_kernelspec_env_value(str(value))};"

            cmd += "nohup"
            for arg in argv_cmd:
                cmd += f" {shlex.quote(str(arg))}"

            cmd += f" >> {shlex.quote(self.kernel_log)} 2>&1 & echo $!"  # return the process id

        return cmd

    def _determine_next_host(self, env_dict: dict) -> str:
        """
        Return the host for this kernel: the host pinned by KERNEL_REMOTE_HOST, which must be
        one of the configured remote hosts, else the next host by round-robin or least-connection.
        """
        remote_host = env_dict.get("KERNEL_REMOTE_HOST")
        if remote_host:
            # Validate before the host is tracked, resolved or contacted.
            remote_host = validate_remote_host(remote_host, self.hosts)
        if self.least_connection:
            next_host = DistributedProcessProxy.kernel_on_host.min_or_remote_host(remote_host)
            DistributedProcessProxy.kernel_on_host.add_kernel_id(next_host, self.kernel_id)
        else:
            next_host = (
                remote_host
                if remote_host
                else self.hosts[DistributedProcessProxy.host_index % self.hosts.__len__()]
            )
            DistributedProcessProxy.host_index += 1

        return next_host

    def _unregister_assigned_host(self) -> None:
        if self.least_connection:
            DistributedProcessProxy.kernel_on_host.delete_kernel_id(self.kernel_id)

    async def confirm_remote_startup(self) -> None:
        """Confirms the remote kernel has started by obtaining connection information from the remote host."""
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            await self.handle_timeout()

            self.log.debug(
                "{}: Waiting to connect.  Host: '{}', KernelID: '{}'".format(
                    i, self.assigned_host, self.kernel_id
                )
            )

            if self.assigned_host:
                ready_to_connect = await self.receive_connection_info()

    async def handle_timeout(self) -> None:
        """Checks to see if the kernel launch timeout has been exceeded while awaiting connection info."""
        await asyncio.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(
            self.start_time, RemoteProcessProxy.get_current_time()
        )

        if time_interval > self.kernel_launch_timeout:
            reason = (
                "Waited too long ({}s) to get connection file.  Check Enterprise Gateway log and kernel "
                "log ({}:{}) for more information.".format(
                    self.kernel_launch_timeout, self.assigned_host, self.kernel_log
                )
            )
            timeout_message = f"KernelID: '{self.kernel_id}' launch timeout due to: {reason}"
            await asyncio.get_event_loop().run_in_executor(None, self.kill)
            self.log_and_raise(http_status_code=500, reason=timeout_message)

    def cleanup(self) -> None:
        """Clean up the proxy."""
        # DistributedProcessProxy can have a tendency to leave zombies, particularly when EG is
        # abruptly terminated.  This extra call to shutdown_lister does the trick.
        self.shutdown_listener()
        self._unregister_assigned_host()
        if self.local_stdout:
            self.local_stdout.close()
            self.local_stdout = None
        super().cleanup()

    def shutdown_listener(self) -> None:
        """Ensure that kernel process is terminated."""
        self.send_signal(signal.SIGTERM)
        super().shutdown_listener()
