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

enterprise_gateway_namespace = os.environ.get('EG_KUBERNETES_NAMESPACE', 'default')
default_kernel_image = os.environ.get('EG_KUBERNETES_KERNEL_IMAGE', 'elyra/kubernetes-kernel-py:dev')

local_ip = localinterfaces.public_ips()[0]

config.load_incluster_config()


class KubernetesProcessProxy(RemoteProcessProxy):
    initial_states = {'Pending', 'Running'}
    final_states = {'Succeeded', 'Failed', 'Unknown'}

    def __init__(self, kernel_manager, proxy_config):
        super(KubernetesProcessProxy, self).__init__(kernel_manager, proxy_config)

        # Determine kernel image to use
        self.kernel_image = default_kernel_image
        if proxy_config.get('image_name'):
            self.kernel_image = proxy_config.get('image_name')
        self.kernel_executor_image = self.kernel_image  # Default the executor image to current image
        if proxy_config.get('executor_image_name'):
            self.kernel_executor_image = proxy_config.get('executor_image_name')
        self.pod_name = ''
        self.kernel_namespace = None
        self.delete_kernel_namespace = False

    def launch_process(self, kernel_cmd, **kw):

        # Set env before superclass call so we see these in the debug output

        # Kubernetes relies on many internal env variables.  Since EG is running in a k8s pod, we will
        # transfer its env to each launched kernel.
        kw['env'].update(os.environ.copy())  # FIXME: Should probably leverage new process-whitelist in JKG #280
        kw['env']['EG_KUBERNETES_KERNEL_IMAGE'] = self.kernel_image
        kw['env']['EG_KUBERNETES_KERNEL_EXECUTOR_IMAGE'] = self.kernel_executor_image
        self.kernel_namespace = self._determine_kernel_namespace(**kw)  # will create namespace if not provided

        super(KubernetesProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info("Kubernetes kernel launched: Kernel image: {}, Namespace: {}, KernelID: {}, cmd: '{}'"
                      .format(self.kernel_image, self.kernel_namespace, self.kernel_id, kernel_cmd))
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

        pod_status = self._get_status()
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
            result = self._terminate_resource()

            if result:
                self.log.debug("KubernetesProcessProxy.kill, pod: {}.{}, kernel ID: {} has been terminated."
                               .format(self.kernel_namespace, self.pod_name, self.kernel_id))
                self.pod_name = None
                result = None  # maintain jupyter contract
            else:
                self.log.warning("KubernetesProcessProxy.kill, pod: {}.{}, kernel ID: {} has not been terminated."
                                 .format(self.kernel_namespace, self.pod_name, self.kernel_id))
        return result

    def cleanup(self):
        # Since kubernetes objects don't go away on their own, we need to perform the same cleanup we'd normally
        # perform on forced kill situations.

        self.kill()
        super(KubernetesProcessProxy, self).cleanup()

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

            pod_status = self._get_status()
            if pod_status:
                self.log.debug("{}: Waiting to connect to k8s pod in namespace '{}'. "
                               "Name: '{}', Status: '{}', Pod IP: '{}', Host IP: '{}', KernelID: '{}'".
                               format(i, self.kernel_namespace, self.pod_name, pod_status.phase, self.assigned_ip,
                                      pod_status.host_ip, self.kernel_id))

                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()
                    self.pid = 0  # We won't send process signals for kubernetes lifecycle management
                    self.pgid = 0
            else:
                self.detect_launch_failure()
                self.log.debug("{}: Waiting to connect to k8s pod in namespace '{}'. "
                               "Name: '{}', Status: 'None', Pod IP: 'None', Host IP: 'None', KernelID: '{}'".
                               format(i, self.kernel_namespace, self.pod_name, self.kernel_id))

    def _get_status(self):
        # Locates the kernel pod using the kernel_id selector.  If the phase indicates Running, the pod's IP
        # is used for the assigned_ip.
        pod_status = None
        ret = client.CoreV1Api().list_namespaced_pod(namespace=self.kernel_namespace,
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

    def _terminate_resource(self):
        # Kubernetes objects don't go away on their own - so we need to tear down the namespace
        # or pod associated with the kernel.  If we created the namespace, then that's our target,
        # else just delete the pod.

        result = False
        body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')

        if self.delete_kernel_namespace:
            object_name = 'namespace'
        else:
            object_name = 'pod'

        # Delete the namespace or pod...
        try:
            # What gets returned from this call is a 'V1Status'.  It looks a bit like JSON but appears to be
            # intentionally obsfucated.  Attempts to load the status field fail due to malformed json.  As a
            # result, we'll see if the status field contains either 'Succeeded' or 'Failed' - since that should
            # indicate the phase value.

            if self.delete_kernel_namespace:
                v1_status = client.CoreV1Api().delete_namespace(name=self.kernel_namespace, body=body)
            else:
                v1_status = client.CoreV1Api().delete_namespaced_pod(namespace=self.kernel_namespace,
                                                                                   body=body, name=self.pod_name)
            if v1_status and v1_status.status:
                termination_stati = ['Succeeded', 'Failed', 'Terminating']
                if any(status in v1_status.status for status in termination_stati):
                    result = True

            if not result:
                self.log.warning("Unable to delete object {}: {}".format(object_name, v1_status))
        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                result = True  # okay if its not found
            else:
                self.log.warning("Error occurred deleting {}: {}".format(object_name, err))
        return result

    def _determine_kernel_namespace(self, **kw):
        # If KERNEL_NAMESPACE was provided, then we assume it already exists.  If not provided, then we'll
        # create the namespace and record that we'll want to delete it as well.

        namespace = kw['env'].get('KERNEL_NAMESPACE')
        if namespace is None:
            namespace = self._create_kernel_namespace(self.get_kernel_username(**kw))
            kw['env']['KERNEL_NAMESPACE'] = namespace  # record in env since kernel needs this
        else:
            self.log.info("KERNEL_NAMESPACE provided by client: {}".format(namespace))

        return namespace

    def _create_kernel_namespace(self, kernel_username):
        # Creates the namespace for the kernel based on the kernel username and kernel id.  Since we're creating
        # the namespace, we'll also note that it should be deleted as well.  In addition, the kernel pod may need
        # to list/create other pods (true for spark-on-k8s), so we'll also create a RoleBinding associated with
        # the namespace's default ServiceAccount.  Since this is always done when creating a namespace, we can
        # delete the RoleBinding when deleting the namespace (no need to record that via another member variable).

        namespace = kernel_username + '-' + self.kernel_id

        # create the namespace ...
        labels = {'app': 'enterprise-gateway', 'component': 'kernel', 'kernel_id': self.kernel_id}
        namespace_metadata = client.V1ObjectMeta(name=namespace, labels=labels)
        body = client.V1Namespace(metadata=namespace_metadata)

        # create the namespace
        try:
            v1_namespace = client.CoreV1Api().create_namespace(body=body)
            self.delete_kernel_namespace = True
            self.log.info("Created kernel namespace: {}".format(namespace))

            # Now create a RoleBinding for this namespace for the default ServiceAccount.  We'll reference
            # the ClusterRole, but that will only be applied for this namespace.  This prevents the need for
            # creating a role each time.
            self._create_role_binding(namespace)

        except Exception as err:
            if self.delete_kernel_namespace:
                self.log.warning("Error occurred creating role binding for namespace '{}': {}, using Enterprise Gateway namespace {}".
                                 format(namespace, err, enterprise_gateway_namespace))
                # delete the namespace since we'll be using the EG namespace...
                body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')
                client.CoreV1Api().delete_namespace(name=namespace, body=body)
                self.log.warning("Deleted kernel namespace: {}".format(namespace))
            else:
                self.log.warning("Error occurred creating namespace '{}': {}, using Enterprise Gateway namespace {}".
                             format(namespace, err, enterprise_gateway_namespace))
            namespace = enterprise_gateway_namespace

        return namespace

    def _create_role_binding(self, namespace):
        # Creates RoleBinding instance for the given namespace.  The role used will be the ClusterRole cluster-admin.
        # Note that roles referenced in RoleBindings are scoped to the namespace so re-using the cluster role prevents
        # the need for creating a new role with each kernel.
        # We will not use a try/except clause here since _create_kernel_namespace will handle exceptions.

        role_binding_name = 'kernel-rb'
        labels = {'app': 'enterprise-gateway', 'component': 'kernel', 'kernel_id': self.kernel_id}
        binding_metadata = client.V1ObjectMeta(name=role_binding_name, labels=labels)
        binding_role_ref = client.V1RoleRef(api_group='', kind='ClusterRole', name='cluster-admin')
        binding_subjects = client.V1Subject(api_group='', kind='ServiceAccount', name='default', namespace=namespace)

        body = client.V1RoleBinding(kind='RoleBinding', metadata=binding_metadata, role_ref=binding_role_ref,
                                    subjects=[binding_subjects])

        client.RbacAuthorizationV1Api().create_namespaced_role_binding(namespace=namespace, body=body)
        self.log.info("Created kernel role-binding '{}' for namespace: {}".format(role_binding_name, namespace))

    def get_process_info(self):
        process_info = super(KubernetesProcessProxy, self).get_process_info()
        process_info.update({'kernel_ns': self.kernel_namespace, 'delete_ns': self.delete_kernel_namespace})
        return process_info

    def load_process_info(self, process_info):
        super(KubernetesProcessProxy, self).load_process_info(process_info)
        self.kernel_namespace = process_info['kernel_ns']
        self.delete_kernel_namespace = process_info['delete_ns']