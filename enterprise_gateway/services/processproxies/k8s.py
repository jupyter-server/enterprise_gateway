# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running in Kubernetes clusters."""

import logging
import os
import re
import urllib3

from kubernetes import client, config

from .container import ContainerProcessProxy
from ..sessions.kernelsessionmanager import KernelSessionManager

urllib3.disable_warnings()

# Default logging level of kubernetes produces too much noise - raise to warning only.
logging.getLogger('kubernetes').setLevel(os.environ.get('EG_KUBERNETES_LOG_LEVEL', logging.WARNING))

enterprise_gateway_namespace = os.environ.get('EG_NAMESPACE', 'default')
default_kernel_service_account_name = os.environ.get('EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME', 'default')
kernel_cluster_role = os.environ.get('EG_KERNEL_CLUSTER_ROLE', 'cluster-admin')
share_gateway_namespace = bool(os.environ.get('EG_SHARED_NAMESPACE', 'False').lower() == 'true')

config.load_incluster_config()


class KubernetesProcessProxy(ContainerProcessProxy):
    """
    Kernel lifecycle management for Kubernetes kernels.
    """
    def __init__(self, kernel_manager, proxy_config):
        super(KubernetesProcessProxy, self).__init__(kernel_manager, proxy_config)

        self.kernel_pod_name = None
        self.kernel_namespace = None
        self.delete_kernel_namespace = False

    async def launch_process(self, kernel_cmd, **kwargs):
        """Launches the specified process within a Kubernetes environment."""
        # Set env before superclass call so we see these in the debug output

        # Kubernetes relies on many internal env variables.  Since EG is running in a k8s pod, we will
        # transfer its env to each launched kernel.
        kwargs['env'] = dict(os.environ, **kwargs['env'])  # FIXME: Should probably use process-whitelist in JKG #280
        self.kernel_pod_name = self._determine_kernel_pod_name(**kwargs)
        self.kernel_namespace = self._determine_kernel_namespace(**kwargs)  # will create namespace if not provided

        await super(KubernetesProcessProxy, self).launch_process(kernel_cmd, **kwargs)
        return self

    def get_initial_states(self):
        """Return list of states indicating container is starting (includes running)."""
        return {'Pending', 'Running'}

    def get_container_status(self, iteration):
        """Return current container state."""
        # Locates the kernel pod using the kernel_id selector.  If the phase indicates Running, the pod's IP
        # is used for the assigned_ip.
        pod_status = None
        kernel_label_selector = "kernel_id=" + self.kernel_id + ",component=kernel"
        ret = client.CoreV1Api().list_namespaced_pod(namespace=self.kernel_namespace,
                                                     label_selector=kernel_label_selector)
        if ret and ret.items:
            pod_info = ret.items[0]
            self.container_name = pod_info.metadata.name
            if pod_info.status:
                pod_status = pod_info.status.phase
                if pod_status == 'Running' and self.assigned_host == '':
                    # Pod is running, capture IP
                    self.assigned_ip = pod_info.status.pod_ip
                    self.assigned_host = self.container_name
                    self.assigned_node_ip = pod_info.status.host_ip

        if iteration:  # only log if iteration is not None (otherwise poll() is too noisy)
            self.log.debug("{}: Waiting to connect to k8s pod in namespace '{}'. "
                           "Name: '{}', Status: '{}', Pod IP: '{}', KernelID: '{}'".
                           format(iteration, self.kernel_namespace, self.container_name, pod_status,
                                  self.assigned_ip, self.kernel_id))

        return pod_status

    def terminate_container_resources(self):
        """Terminate any artifacts created on behalf of the container's lifetime."""
        # Kubernetes objects don't go away on their own - so we need to tear down the namespace
        # or pod associated with the kernel.  If we created the namespace and we're not in the
        # the process of restarting the kernel, then that's our target, else just delete the pod.

        result = False
        body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')

        if self.delete_kernel_namespace and not self.kernel_manager.restarting:
            object_name = 'namespace'
        else:
            object_name = 'pod'

        # Delete the namespace or pod...
        try:
            # What gets returned from this call is a 'V1Status'.  It looks a bit like JSON but appears to be
            # intentionally obfuscated.  Attempts to load the status field fail due to malformed json.  As a
            # result, we'll see if the status field contains either 'Succeeded' or 'Failed' - since that should
            # indicate the phase value.

            if self.delete_kernel_namespace and not self.kernel_manager.restarting:
                v1_status = client.CoreV1Api().delete_namespace(name=self.kernel_namespace, body=body)
            else:
                v1_status = client.CoreV1Api().delete_namespaced_pod(namespace=self.kernel_namespace,
                                                                     body=body, name=self.container_name)
            if v1_status and v1_status.status:
                termination_stati = ['Succeeded', 'Failed', 'Terminating']
                if any(status in v1_status.status for status in termination_stati):
                    result = True

            if not result:
                self.log.warning("Unable to delete {}: {}".format(object_name, v1_status))
        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 404:
                result = True  # okay if its not found
            else:
                self.log.warning("Error occurred deleting {}: {}".format(object_name, err))

        if result:
            self.log.debug("KubernetesProcessProxy.terminate_container_resources, pod: {}.{}, kernel ID: {} has "
                           "been terminated.".format(self.kernel_namespace, self.container_name, self.kernel_id))
            self.container_name = None
            result = None  # maintain jupyter contract
        else:
            self.log.warning("KubernetesProcessProxy.terminate_container_resources, pod: {}.{}, kernel ID: {} has "
                             "not been terminated.".format(self.kernel_namespace, self.container_name, self.kernel_id))
        return result

    def _determine_kernel_pod_name(self, **kwargs):
        pod_name = kwargs['env'].get('KERNEL_POD_NAME')
        if pod_name is None:
            pod_name = KernelSessionManager.get_kernel_username(**kwargs) + '-' + self.kernel_id

        # Rewrite pod_name to be compatible with DNS name convention
        # And put back into env since kernel needs this
        pod_name = re.sub('[^0-9a-z]+', '-', pod_name.lower())
        while pod_name.startswith('-'):
            pod_name = pod_name[1:]
        while pod_name.endswith('-'):
            pod_name = pod_name[:-1]
        kwargs['env']['KERNEL_POD_NAME'] = pod_name

        return pod_name

    def _determine_kernel_namespace(self, **kwargs):

        # Since we need the service account name regardless of whether we're creating the namespace or not,
        # get it now.
        service_account_name = KubernetesProcessProxy._determine_kernel_service_account_name(**kwargs)

        # If KERNEL_NAMESPACE was provided, then we assume it already exists.  If not provided, then we'll
        # create the namespace and record that we'll want to delete it as well.
        namespace = kwargs['env'].get('KERNEL_NAMESPACE')
        if namespace is None:
            # check if share gateway namespace is configured...
            if share_gateway_namespace:  # if so, set to EG namespace
                namespace = enterprise_gateway_namespace
                self.log.warning("Shared namespace has been configured.  All kernels will reside in EG namespace: {}".
                                 format(namespace))
            else:
                namespace = self._create_kernel_namespace(service_account_name)
            kwargs['env']['KERNEL_NAMESPACE'] = namespace  # record in env since kernel needs this
        else:
            self.log.info("KERNEL_NAMESPACE provided by client: {}".format(namespace))

        return namespace

    @staticmethod
    def _determine_kernel_service_account_name(**kwargs):
        # Check if an account name was provided.  If not, set to the default name (which can be set
        # from the EG env as well).  Finally, ensure the env value is set.
        service_account_name = kwargs['env'].get('KERNEL_SERVICE_ACCOUNT_NAME', default_kernel_service_account_name)
        kwargs['env']['KERNEL_SERVICE_ACCOUNT_NAME'] = service_account_name
        return service_account_name

    def _create_kernel_namespace(self, service_account_name):
        # Creates the namespace for the kernel based on the kernel username and kernel id.  Since we're creating
        # the namespace, we'll also note that it should be deleted as well.  In addition, the kernel pod may need
        # to list/create other pods (true for spark-on-k8s), so we'll also create a RoleBinding associated with
        # the namespace's default ServiceAccount.  Since this is always done when creating a namespace, we can
        # delete the RoleBinding when deleting the namespace (no need to record that via another member variable).

        namespace = self.kernel_pod_name

        # create the namespace ...
        labels = {'app': 'enterprise-gateway', 'component': 'kernel', 'kernel_id': self.kernel_id}
        namespace_metadata = client.V1ObjectMeta(name=namespace, labels=labels)
        body = client.V1Namespace(metadata=namespace_metadata)

        # create the namespace
        try:
            client.CoreV1Api().create_namespace(body=body)
            self.delete_kernel_namespace = True
            self.log.info("Created kernel namespace: {}".format(namespace))

            # Now create a RoleBinding for this namespace for the default ServiceAccount.  We'll reference
            # the ClusterRole, but that will only be applied for this namespace.  This prevents the need for
            # creating a role each time.
            self._create_role_binding(namespace, service_account_name)
        except Exception as err:
            if isinstance(err, client.rest.ApiException) and err.status == 409 and self.kernel_manager.restarting:
                self.delete_kernel_namespace = True  # okay if ns already exists and restarting, still mark for delete
                self.log.info("Re-using kernel namespace: {}".format(namespace))
            else:
                if self.delete_kernel_namespace:
                    reason = "Error occurred creating role binding for namespace '{}': {}".format(namespace, err)
                    # delete the namespace since we'll be using the EG namespace...
                    body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')
                    client.CoreV1Api().delete_namespace(name=namespace, body=body)
                    self.log.warning("Deleted kernel namespace: {}".format(namespace))
                else:
                    reason = "Error occurred creating namespace '{}': {}".format(namespace, err)
                self.log_and_raise(http_status_code=500, reason=reason)

        return namespace

    def _create_role_binding(self, namespace, service_account_name):
        # Creates RoleBinding instance for the given namespace.  The role used will be the ClusterRole named by
        # EG_KERNEL_CLUSTER_ROLE.
        # Note that roles referenced in RoleBindings are scoped to the namespace so re-using the cluster role prevents
        # the need for creating a new role with each kernel.
        # The ClusterRole will be bound to the kernel service user identified by KERNEL_SERVICE_ACCOUNT_NAME then
        # EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME, respectively.
        # We will not use a try/except clause here since _create_kernel_namespace will handle exceptions.

        role_binding_name = kernel_cluster_role  # use same name for binding as cluster role
        labels = {'app': 'enterprise-gateway', 'component': 'kernel', 'kernel_id': self.kernel_id}
        binding_metadata = client.V1ObjectMeta(name=role_binding_name, labels=labels)
        binding_role_ref = client.V1RoleRef(api_group='', kind='ClusterRole', name=kernel_cluster_role)
        binding_subjects = client.V1Subject(api_group='', kind='ServiceAccount', name=service_account_name,
                                            namespace=namespace)

        body = client.V1RoleBinding(kind='RoleBinding', metadata=binding_metadata, role_ref=binding_role_ref,
                                    subjects=[binding_subjects])

        client.RbacAuthorizationV1Api().create_namespaced_role_binding(namespace=namespace, body=body)
        self.log.info("Created kernel role-binding '{}' in namespace: {} for service account: {}".
                      format(role_binding_name, namespace, service_account_name))

    def get_process_info(self):
        """Captures the base information necessary for kernel persistence relative to kubernetes."""
        process_info = super(KubernetesProcessProxy, self).get_process_info()
        process_info.update({'kernel_ns': self.kernel_namespace, 'delete_ns': self.delete_kernel_namespace})
        return process_info

    def load_process_info(self, process_info):
        """Loads the base information necessary for kernel persistence relative to kubernetes."""
        super(KubernetesProcessProxy, self).load_process_info(process_info)
        self.kernel_namespace = process_info['kernel_ns']
        self.delete_kernel_namespace = process_info['delete_ns']
