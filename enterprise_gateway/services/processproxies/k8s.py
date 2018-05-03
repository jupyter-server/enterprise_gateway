# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import time
import tornado
import signal
import logging
from tornado import web
from socket import *
from jupyter_client import launch_kernel, localinterfaces
from .processproxy import RemoteProcessProxy
from kubernetes import client, config
import urllib3
urllib3.disable_warnings()

# Default logging level of kubernetes produces too much noise - raise to warning only.
logging.getLogger('kubernetes').setLevel(os.getenv('EG_KUBERNETES_LOG_LEVEL', logging.WARNING))


poll_interval = float(os.environ.get('EG_POLL_INTERVAL', '0.5'))

# FIXME - promote to options
k8s_config_file = os.environ.get('EG_KUBERNETES_CONFIG', '~/.kube/config')
k8s_namespace = os.environ.get('EG_KUBERNETES_NAMESPACE', 'default')
k8s_kernel_image = os.environ.get('EG_KUBERNETES_KERNEL_IMAGE', 'elyra/kubernetes-kernel:dev')

local_ip = localinterfaces.public_ips()[0]

config.load_kube_config(config_file=k8s_config_file)


class KubernetesProcessProxy(RemoteProcessProxy):
    initial_states = {'Pending', 'Running'}
    final_states = {'Succeeded', 'Failed', 'Unknown'}

    def __init__(self, kernel_manager, proxy_config):
        super(KubernetesProcessProxy, self).__init__(kernel_manager, proxy_config)
        if proxy_config.get('remote_hosts'):
            self.hosts = proxy_config.get('remote_hosts').split(',')
        else:
            self.hosts = kernel_manager.parent.parent.remote_hosts  # from command line or env
        self.service_name = ''

    def launch_process(self, kernel_cmd, **kw):
        super(KubernetesProcessProxy, self).launch_process(kernel_cmd, **kw)

        kw['env']['EG_KUBERNETES_CONFIG'] = k8s_config_file
        kw['env']['EG_KUBERNETES_NAMESPACE'] = k8s_namespace
        kw['env']['EG_KUBERNETES_KERNEL_IMAGE'] = k8s_kernel_image
        kw['env']['EG_KERNEL_RESPONSE_ADDRESS'] = self.kernel_manager.response_address

        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info("Kubernetes kernel launched: pid: {}, KernelID: {}, cmd: '{}'"
                      .format(self.pid, self.kernel_id, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

        return self

    def poll(self):
        """Submitting a new kernel to kubernetes will take a while to be Running.
        Thus kernel ID will probably not be available immediately for poll.
        So will regard the pod as active when no status is available or one of the initial
        phases.

        :return: None if the pod cannot be found or its in an initial phase. Otherwise False. 
        """
        result = False

        pod_status = self.get_status()
        if pod_status is None or pod_status.phase in KubernetesProcessProxy.initial_states:
            result = None

        return result

    def send_signal(self, signum):
        """Currently only support 0 as poll and other as kill.

        :param signum
        :return: 
        """
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            # This is very likely an interrupt signal, so defer to the super class
            # which should use the communication port.
            return super(KubernetesProcessProxy, self).send_signal(signum)

    def kill(self):
        """Kill a kernel.
        :return: None if the job is gracefully terminated, False otherwise.
        """

        result = None

        if self.service_name:  # We only have something to terminate if we have a name
            result = self.terminate_job()

            if result:
                self.log.debug("KubernetesProcessProxy.kill, job: {}, kernel ID: {} has been terminated."
                           .format(self.service_name, self.kernel_id))
                self.service_name = None
                result = None  # maintain jupyter contract
            else:
                self.log.warning("KubernetesProcessProxy.kill, job: {}, kernel ID: {} has not been terminated."
                           .format(self.service_name, self.kernel_id))
        return result

    def cleanup(self):
        # Since kubernetes objects don't go away on their own, we need to perform the same cleanup we'd normally
        # perform on forced kill situations.

        self.kill()
        super(RemoteProcessProxy, self).cleanup()

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

            pod_status = self.get_status()
            if pod_status:
                self.log.debug("{}: Waiting to connect to k8s pod. "
                               "Status: '{}', Pod IP: '{}', Host IP: '{}', KernelID: '{}'".
                           format(i, pod_status.phase, self.assigned_ip, pod_status.host_ip, self.kernel_id))

                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()
                    self.pid = 0  # We won't send process signals for kubernetes lifecycle management
                    self.pgid = 0
            else:
                self.log.debug("{}: Waiting to connect to k8s pod. "
                               "Status: 'None', Pod IP: 'None', Host IP: 'None', KernelID: '{}'".
                           format(i, self.kernel_id))

    def get_status(self):
        # Locates the kernel pod using the kernel_id selector.  If the phase indicates Running, the pod's service
        # is selected where the service's cluster IP is then used, which "fronts" the pod's IP via an endpoint.
        pod_status = None
        ret = client.CoreV1Api(client.ApiClient()).list_namespaced_pod(namespace=k8s_namespace,
                                                     label_selector="kernel_id=" + self.kernel_id)
        if ret and ret.items:
            pod_info = ret.items[0]
            if pod_info.status:
                if pod_info.status.phase == 'Running' and self.assigned_host == '':
                    # Pod is Running - get the cluster IP from its fronting service
                    ret = client.CoreV1Api(client.ApiClient()).list_namespaced_service(namespace=k8s_namespace,
                                                                     label_selector="kernel_id=" + self.kernel_id)
                    if ret and ret.items:
                        svc_info = ret.items[0]
                        self.service_name = svc_info.metadata.name
                        self.assigned_ip = svc_info.spec.cluster_ip
                        self.assigned_host = svc_info.spec.cluster_ip
                return pod_info.status
        return pod_status

    def terminate_job(self):
        # Kubernetes objects don't go away on their own - so we need to tear down the service and job
        # associated with the kernel.
        result = True
        body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')

        # First delete the service,
        try:
            ret = client.CoreV1Api(client.ApiClient()).delete_namespaced_service(namespace=k8s_namespace,
                                                                                 name=self.service_name)
            if ret and ret.status != 'Success':
                self.log.warning("Failure occurred deleting service: {}".format(ret))
        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                pass  # okay if its not found
            else:
                self.log.warning("Error occurred deleting service: {}".format(err))
                result = False

        # then the job...
        try:
            ret = client.BatchV1Api(client.ApiClient()).delete_namespaced_job(namespace=k8s_namespace, body=body,
                                                    name=self.service_name)
            if ret and ret.status != 'Success':
                self.log.warning("Failure occurred deleting job: {}".format(ret))
        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                pass  # okay if its not found
            else:
                self.log.warning("Error occurred deleting job: {}".format(err))
                result = False
        return result

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

