# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import json
import time
from socket import *
from .processproxy import RemoteProcessProxy

poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
kernel_log_dir = os.getenv("EG_KERNEL_LOG_DIR", '/tmp')  # would prefer /var/log, but its only writable by root


class DistributedProcessProxy(RemoteProcessProxy):
    host_index = 0

    def __init__(self, kernel_manager, proxy_config):
        super(DistributedProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.kernel_log = None
        if proxy_config.get('remote_hosts'):
            self.hosts = proxy_config.get('remote_hosts').split(',')
        else:
            self.hosts = kernel_manager.parent.parent.remote_hosts  # from command line or env

    def launch_process(self, kernel_cmd, **kw):
        super(DistributedProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.assigned_host = self.determine_next_host()
        self.ip = gethostbyname(self.assigned_host)  # convert to ip if host is provided
        self.assigned_ip = self.ip

        cmd = self.build_startup_command(kernel_cmd, **kw)
        self.log.debug("Invoking cmd: '{}' on host: {}".format(cmd, self.assigned_host))
        result_pid = 'bad_pid'  # purposely initialize to bad int value

        try:
            result = self.rsh(self.ip, cmd)
        except Exception as e:
            error_message = "Failure occurred starting remote kernel on '{}'. Exception: '{}'.".format(self.ip, e)
            self.log_and_raise(http_status_code=500, reason=error_message)

        for line in result:
            result_pid = line.strip()

        try:
            self.pid = int(result_pid)
        except ValueError:
            error_message = "Failure occurred starting remote kernel on '{}'.  Returned result: {}".\
                format(self.ip, result)
            self.log_and_raise(http_status_code=500, reason=error_message)

        self.log.info("Remote kernel launched on '{}', pid: {}, ID: {}, Log file: {}:{}, Command: '{}'.  ".
                      format(self.assigned_host, self.pid, self.kernel_id, self.assigned_host, self.kernel_log, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

        return self

    def build_startup_command(self, argv_cmd, **kw):
        """
        Builds the command to invoke by concatenating envs from kernelspec followed by the kernel argvs.

        We also force nohup, redirection to a file and place in background, then follow with an echo
        for the background pid.
        """
        cmd = ''
        # Add additional envs not in kernelspec...
        env_dict = kw['env']

        kuser = env_dict.get('KERNEL_USERNAME')
        if kuser:
            cmd += 'export KERNEL_USERNAME="{}";'.format(kuser)
        kid = env_dict.get('KERNEL_ID')
        if kid:
            cmd += 'export KERNEL_ID="{}";'.format(kid)
        impersonation = env_dict.get('EG_IMPERSONATION_ENABLED')
        if impersonation:
            cmd += 'export EG_IMPERSONATION_ENABLED="{}";'.format(impersonation)

        for key, value in self.kernel_manager.kernel_spec.env.items():
            cmd += "export {}={};".format(key, json.dumps(value).replace("'", "''"))

        cmd += 'nohup'
        for arg in argv_cmd:
            cmd += ' {}'.format(arg)

        self.kernel_log = os.path.join(kernel_log_dir, "kernel-{}.log".format(kid))
        cmd += ' >> {} 2>&1 & echo $!'.format(self.kernel_log)

        return cmd

    def determine_next_host(self):
        next_host = self.hosts[DistributedProcessProxy.host_index % self.hosts.__len__()]
        DistributedProcessProxy.host_index += 1
        return next_host

    def confirm_remote_startup(self, kernel_cmd, **kw):
        """ Confirms the remote application has started by obtaining connection information from the remote
            host based on the connection file mode.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            self.handle_timeout()

            self.log.debug("{}: Waiting to connect.  Host: '{}', KernelID: '{}'".
                           format(i, self.assigned_host, self.kernel_id))

            if self.assigned_host != '':
                ready_to_connect = self.receive_connection_info()

    def handle_timeout(self):
        time.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            reason = "Waited too long ({}s) to get connection file.  Check Enterprise Gateway log and kernel " \
                     "log ({}:{}) for more information.".\
                format(self.kernel_launch_timeout, self.assigned_host, self.kernel_log)
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.kill()
            self.log_and_raise(http_status_code=500, reason=timeout_message)
