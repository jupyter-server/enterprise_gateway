# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code used for the generic distribution of kernels across a set of hosts."""

import asyncio
import json
import os
import signal

from subprocess import STDOUT
from socket import gethostbyname

from jupyter_client import launch_kernel

from .processproxy import RemoteProcessProxy, BaseProcessProxyABC

poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
kernel_log_dir = os.getenv("EG_KERNEL_LOG_DIR", '/tmp')  # would prefer /var/log, but its only writable by root


class DistributedProcessProxy(RemoteProcessProxy):
    """Manages the lifecycle of kernels distributed across a set of hosts."""
    host_index = 0

    def __init__(self, kernel_manager, proxy_config):
        super(DistributedProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.kernel_log = None
        if proxy_config.get('remote_hosts'):
            self.hosts = proxy_config.get('remote_hosts').split(',')
        else:
            self.hosts = kernel_manager.remote_hosts  # from command line or env

    async def launch_process(self, kernel_cmd, **kwargs):
        """Launches a kernel process on a selected host."""
        await super(DistributedProcessProxy, self).launch_process(kernel_cmd, **kwargs)

        self.assigned_host = self._determine_next_host()
        self.ip = gethostbyname(self.assigned_host)  # convert to ip if host is provided
        self.assigned_ip = self.ip

        try:
            result_pid = self._launch_remote_process(kernel_cmd, **kwargs)
            self.pid = int(result_pid)
        except Exception as e:
            error_message = "Failure occurred starting kernel on '{}'.  Returned result: {}".\
                format(self.ip, e)
            self.log_and_raise(http_status_code=500, reason=error_message)

        self.log.info("Kernel launched on '{}', pid: {}, ID: {}, Log file: {}:{}, Command: '{}'.  ".
                      format(self.assigned_host, self.pid, self.kernel_id, self.assigned_host,
                             self.kernel_log, kernel_cmd))
        await self.confirm_remote_startup()
        return self

    def _launch_remote_process(self, kernel_cmd, **kwargs):
        """
            Launch the kernel as indicated by the argv stanza in the kernelspec.  Note that this method
            will bypass use of ssh if the remote host is also the local machine.
        """

        cmd = self._build_startup_command(kernel_cmd, **kwargs)
        self.log.debug("Invoking cmd: '{}' on host: {}".format(cmd, self.assigned_host))
        result_pid = 'bad_pid'  # purposely initialize to bad int value

        if BaseProcessProxyABC.ip_is_local(self.ip):
            # launch the local command with redirection in place
            self.local_proc = launch_kernel(cmd, stdout=open(self.kernel_log, mode='w'), stderr=STDOUT, **kwargs)
            result_pid = str(self.local_proc.pid)
        else:
            # launch remote command via ssh
            result = self.rsh(self.ip, cmd)
            for line in result:
                result_pid = line.strip()

        return result_pid

    def _build_startup_command(self, argv_cmd, **kwargs):
        """
        Builds the command to invoke by concatenating envs from kernelspec followed by the kernel argvs.

        We also force nohup, redirection to a file and place in background, then follow with an echo
        for the background pid.

        Note: We optimize for the local case and just return the existing command.
        """

        # Optimized case needs to also redirect the kernel output, so unconditionally compose kernel_log
        env_dict = kwargs['env']
        kid = env_dict.get('KERNEL_ID')
        self.kernel_log = os.path.join(kernel_log_dir, "kernel-{}.log".format(kid))

        if BaseProcessProxyABC.ip_is_local(self.ip):  # We're local so just use what we're given
            cmd = argv_cmd
        else:  # Add additional envs, including those in kernelspec
            cmd = ''
            if kid:
                cmd += 'export KERNEL_ID="{}";'.format(kid)

            kuser = env_dict.get('KERNEL_USERNAME')
            if kuser:
                cmd += 'export KERNEL_USERNAME="{}";'.format(kuser)

            impersonation = env_dict.get('EG_IMPERSONATION_ENABLED')
            if impersonation:
                cmd += 'export EG_IMPERSONATION_ENABLED="{}";'.format(impersonation)

            for key, value in self.kernel_manager.kernel_spec.env.items():
                cmd += "export {}={};".format(key, json.dumps(value).replace("'", "''"))

            cmd += 'nohup'
            for arg in argv_cmd:
                cmd += ' {}'.format(arg)

            cmd += ' >> {} 2>&1 & echo $!'.format(self.kernel_log)  # return the process id

        return cmd

    def _determine_next_host(self):
        """Simple round-robin index into list of hosts."""
        next_host = self.hosts[DistributedProcessProxy.host_index % self.hosts.__len__()]
        DistributedProcessProxy.host_index += 1
        return next_host

    async def confirm_remote_startup(self):
        """ Confirms the remote kernel has started by obtaining connection information from the remote host."""
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            await self.handle_timeout()

            self.log.debug("{}: Waiting to connect.  Host: '{}', KernelID: '{}'".
                           format(i, self.assigned_host, self.kernel_id))

            if self.assigned_host != '':
                ready_to_connect = await self.receive_connection_info()

    async def handle_timeout(self):
        """Checks to see if the kernel launch timeout has been exceeded while awaiting connection info."""
        await asyncio.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            reason = "Waited too long ({}s) to get connection file.  Check Enterprise Gateway log and kernel " \
                     "log ({}:{}) for more information.".\
                format(self.kernel_launch_timeout, self.assigned_host, self.kernel_log)
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.kill()
            self.log_and_raise(http_status_code=500, reason=timeout_message)

    def cleanup(self):
        # DistributedProcessProxy can have a tendency to leave zombies, particularly when EG is
        # abruptly terminated.  This extra call to shutdown_lister does the trick.
        self.shutdown_listener()
        super(RemoteProcessProxy, self).cleanup()

    def shutdown_listener(self):
        """Ensure that kernel process is terminated."""
        self.send_signal(signal.SIGTERM)
        super(DistributedProcessProxy, self).shutdown_listener()
