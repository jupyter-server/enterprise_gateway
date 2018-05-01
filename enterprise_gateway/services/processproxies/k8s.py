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
from kubernetes import client, config

poll_interval = float(os.environ.get('EG_POLL_INTERVAL', '0.5'))
k8s_config_file = os.environ.get('EG_KUBERNETES_CONFIG', '~/.kube/config')

local_ip = localinterfaces.public_ips()[0]

config.load_kube_config(config_file=k8s_config_file)


class KubernetesProcessProxy(RemoteProcessProxy):
    host_index = 0

    def __init__(self, kernel_manager, proxy_config):
        super(KubernetesProcessProxy, self).__init__(kernel_manager, proxy_config)
        if proxy_config.get('remote_hosts'):
            self.hosts = proxy_config.get('remote_hosts').split(',')
        else:
            self.hosts = kernel_manager.parent.parent.remote_hosts  # from command line or env
        self.k8s_client = client.CoreV1Api()

    def launch_process(self, kernel_cmd, **kw):
        super(KubernetesProcessProxy, self).launch_process(kernel_cmd, **kw)

        kw['env']['EG_KUBERNETES_CONFIG'] = k8s_config_file

        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip

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

            pod_status = self.get_k8s_status()

            if pod_status:
                self.log.debug("{}: Waiting to connect to k8s pod. "
                               "Status: '{}', Pod IP: '{}', Host IP: '{}', KernelID: '{}'".
                           format(i, pod_status.phase, self.assigned_ip, pod_status.host_ip, self.kernel_id))

                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()
            else:
                self.log.debug("{}: Waiting to connect to k8s pod. "
                               "Status: 'None', Pod IP: 'None', Host IP: 'None', KernelID: '{}'".
                           format(i, self.kernel_id))

    def get_k8s_status(self):
        # Gets the current application state using the application_id already obtained.  Once the assigned host
        # has been identified, it is nolonger accessed.
        app_state = None
        ret = self.k8s_client.list_pod_for_all_namespaces(label_selector="kernel_id=" + self.kernel_id)

        if ret and ret.items:
            pod_info = ret.items[0]
            if pod_info.status:
                if pod_info.status.phase == 'Running' and self.assigned_host == '':
                    ret = self.k8s_client.list_service_for_all_namespaces(label_selector="kernel_id=" + self.kernel_id)
                    self.assigned_host = pod_info.status.pod_ip  # ? should be host_ip?
                    self.assigned_ip = pod_info.status.pod_ip
                    self.assigned_ip = ret.items[0].spec.cluster_ip
                return pod_info.status
        return None

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

