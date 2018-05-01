# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import json
import time
import tornado
from tornado import web
from socket import *
from jupyter_client import launch_kernel, localinterfaces
from .processproxy import RemoteProcessProxy

poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
kernel_log_dir = os.getenv("EG_KERNEL_LOG_DIR", '/tmp')  # would prefer /var/log, but its only writable by root

local_ip = localinterfaces.public_ips()[0]


class KubernetesProcessProxy(RemoteProcessProxy):
    host_index = 0

    def __init__(self, kernel_manager, proxy_config):
        super(KubernetesProcessProxy, self).__init__(kernel_manager, proxy_config)
        if proxy_config.get('remote_hosts'):
            self.hosts = proxy_config.get('remote_hosts').split(',')
        else:
            self.hosts = kernel_manager.parent.parent.remote_hosts  # from command line or env

    def launch_process(self, kernel_cmd, **kw):
        super(KubernetesProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip
        self.assigned_ip = local_ip  # FIXME
        self.assigned_host = 'localhost'  # FIXME

        self.log.info("Kubernetes kernel launched: pid: {}, KernelID: {}, cmd: '{}'"
                      .format(self.pid, self.kernel_id, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

        return self

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

            #if self.assigned_host != '':
            ready_to_connect = self.receive_connection_info()

    def handle_timeout(self):
        time.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            error_http_code = 500
            reason = "Waited too long ({}s) to get connection file".format(self.kernel_launch_timeout)
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log.error(timeout_message)
            self.kill()
            raise tornado.web.HTTPError(error_http_code, timeout_message)

