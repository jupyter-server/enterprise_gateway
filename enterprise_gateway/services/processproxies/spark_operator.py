# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
import re
from kubernetes import client

from .crd import CustomResourceProxy
from ..sessions.kernelsessionmanager import KernelSessionManager

enterprise_gateway_namespace = os.environ.get('EG_NAMESPACE', 'default')


class SparkOperatorProcessProxy(CustomResourceProxy):
    def __init__(self, kernel_manager, proxy_config):
        super(SparkOperatorProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.kernel_namespace = None
        self.group = 'sparkoperator.k8s.io'
        self.version = 'v1beta2'
        self.plural = 'sparkapplications'

    async def launch_process(self, kernel_cmd, **kwargs):
        kwargs['env'] = dict(os.environ, **kwargs['env'])  # FIXME: Should probably use process-whitelist in JKG #280
        self.kernel_resource_name = self._determine_kernel_resource_name(**kwargs)
        self.kernel_namespace = self._determine_kernel_namespace(**kwargs)  # will create namespace if not provided

        await super(SparkOperatorProcessProxy, self).launch_process(kernel_cmd, **kwargs)
        return self

    def get_resource_status(self, iteration):
        resource_status = None

        try:
            custom_resource = client.CustomObjectsApi().get_namespaced_custom_object(self.group, self.version,
                                                                                     self.kernel_namespace,
                                                                                     self.plural,
                                                                                     self.kernel_resource_name)

            if custom_resource:
                resource_status = custom_resource['status']['applicationState']['state']
                pod_name = custom_resource['status']['driverInfo']['podName']
                pod_info = client.CoreV1Api().read_namespaced_pod(pod_name, self.kernel_namespace)
            else:
                pod_info = None
        except Exception:
            pod_info = None

        if pod_info and pod_info.status:
            pod_status = pod_info.status.phase
            if pod_status == 'Running' and self.assigned_host == '':
                self.assigned_ip = pod_info.status.pod_ip
                self.assigned_host = pod_info.metadata.name
                self.assigned_node_ip = pod_info.status.host_ip

        if iteration:
            self.log.debug("{}: Waiting to connect to k8s custom resource in namespace '{}'. "
                           "Name: '{}', Status: '{}', Pod IP: '{}', KernelID: '{}'".
                           format(iteration, self.kernel_namespace, self.kernel_resource_name, resource_status,
                                  self.assigned_ip, self.kernel_id))

        return resource_status

    def get_initial_states(self):
        return {'SUBMITTED', 'RUNNING'}

    def _determine_kernel_resource_name(self, **kwargs):
        resource_name = kwargs['env'].get('KERNEL_RESOURCE_NAME',
                                          KernelSessionManager.get_kernel_username(**kwargs) + '-' + self.kernel_id)

        resource_name = re.sub('[^0-9a-z]+', '-', resource_name.lower())
        while resource_name.startswith('-'):
            resource_name = resource_name[1:]
        while resource_name.endswith('-'):
            resource_name = resource_name[:-1]
        kwargs['env']['KERNEL_RESOURCE_NAME'] = resource_name

        return resource_name

    def _determine_kernel_namespace(self, **kwargs):
        namespace = kwargs['env'].get('KERNEL_NAMESPACE')
        if namespace is None:
            kwargs['env']['KERNEL_NAMESPACE'] = enterprise_gateway_namespace
        else:
            self.log.info("KERNEL_NAMESPACE provided by client: {}".format(namespace))

        return namespace
