# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import signal
import logging
from socket import *
from jupyter_client import launch_kernel, localinterfaces
from .processproxy import RemoteProcessProxy
from kubernetes import client, config
import urllib3
urllib3.disable_warnings()

# Default logging level of kubernetes produces too much noise - raise to warning only.
logging.getLogger('kubernetes').setLevel(os.getenv('EG_KUBERNETES_LOG_LEVEL', logging.WARNING))

k8s_namespace = os.environ.get('EG_KUBERNETES_NAMESPACE', 'default')
k8s_default_kernel_image = os.environ.get('EG_KUBERNETES_KERNEL_IMAGE', 'elyra/kubernetes-kernel:dev')

local_ip = localinterfaces.public_ips()[0]

config.load_incluster_config()


class KubernetesProcessProxy(RemoteProcessProxy):
    initial_states = {'Pending', 'Running'}
    final_states = {'Succeeded', 'Failed', 'Unknown'}

    def __init__(self, kernel_manager, proxy_config):
        super(KubernetesProcessProxy, self).__init__(kernel_manager, proxy_config)

        # Determine kernel image to use
        self.k8s_kernel_image = k8s_default_kernel_image
        if proxy_config.get('image_name'):
            self.k8s_kernel_image = proxy_config.get('image_name')
        self.pod_name = ''

    def launch_process(self, kernel_cmd, **kw):

        # Set env before superclass call so we see these in the debug output

        # Kubernetes relies on many internal env variables.  Since EG is running in a k8s pod, we will
        # transfer its env to each launched kernel.
        kw['env'].update(os.environ.copy())
        kw['env']['EG_KUBERNETES_KERNEL_IMAGE'] = self.k8s_kernel_image

        super(KubernetesProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info("Kubernetes kernel launched: Kernel image: {}, KernelID: {}, cmd: '{}'"
                      .format(self.k8s_kernel_image, self.kernel_id, kernel_cmd))
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
        :return: None if the pod is gracefully terminated, False otherwise.
        """

        result = None

        if self.pod_name:  # We only have something to terminate if we have a name
            result = self.terminate_pod()

            if result:
                self.log.debug("KubernetesProcessProxy.kill, pod: {}, kernel ID: {} has been terminated."
                               .format(self.pod_name, self.kernel_id))
                self.pod_name = None
                result = None  # maintain jupyter contract
            else:
                self.log.warning("KubernetesProcessProxy.kill, pod: {}, kernel ID: {} has not been terminated."
                                 .format(self.pod_name, self.kernel_id))
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
                               "Name: '{}', Status: '{}', Pod IP: '{}', Host IP: '{}', KernelID: '{}'".
                               format(i, self.pod_name, pod_status.phase, self.assigned_ip, pod_status.host_ip,
                                      self.kernel_id))

                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()
                    self.pid = 0  # We won't send process signals for kubernetes lifecycle management
                    self.pgid = 0
            else:
                self.log.debug("{}: Waiting to connect to k8s pod. "
                               "Name: '{}', Status: 'None', Pod IP: 'None', Host IP: 'None', KernelID: '{}'".
                               format(i, self.pod_name, self.kernel_id))

    def get_status(self):
        # Locates the kernel pod using the kernel_id selector.  If the phase indicates Running, the pod's IP
        # is used for the assigned_ip.
        pod_status = None
        ret = client.CoreV1Api(client.ApiClient()).list_namespaced_pod(namespace=k8s_namespace,
                                                     label_selector="kernel_id=" + self.kernel_id)
        if ret and ret.items:
            pod_info = ret.items[0]
            self.pod_name = pod_info.metadata.name
            if pod_info.status:
                if pod_info.status.phase == 'Running' and self.assigned_host == '':
                    # Pod is running, capture IP
                    self.assigned_ip = pod_info.status.pod_ip
                    self.assigned_host = pod_info.status.pod_ip
                return pod_info.status
        return pod_status

    def terminate_pod(self):
        # Kubernetes objects don't go away on their own - so we need to tear down the pod
        # associated with the kernel.
        result = False
        body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')

        # Delete the pod...
        try:
            # What gets returned from this call is a 'V1Status'.  It looks a bit like JSON but appears to be
            # intentionally obsfucated.  Attempts to load the status field fail due to malformed json.  As a
            # result, we'll see if the status field contains either 'Succeeded' or 'Failed' - since that should
            # indicate the phase value.
            # FIXME - we may want to revisit this.
            v1_status = client.CoreV1Api(client.ApiClient()).delete_namespaced_pod(namespace=k8s_namespace, body=body,
                                                                                   name=self.pod_name)
            if v1_status and v1_status.status:
                if 'Succeeded' in v1_status.status or 'Failed' in v1_status.status:
                    result = True
                else:
                    self.log.debug("Pod deletion status: '{}'".format(v1_status))

            if not result:
                self.log.warning("Failure occurred deleting pod: {}".format(v1_status))
        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                result = True  # okay if its not found
            else:
                self.log.warning("Error occurred deleting pod: {}".format(err))
        return result
