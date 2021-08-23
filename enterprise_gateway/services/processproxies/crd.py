# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running based on k8s custom resource."""

from .k8s import KubernetesProcessProxy
from kubernetes import client


class CustomResourceProxy(KubernetesProcessProxy):
    group = version = plural = None
    custom_resource_template_name = None
    kernel_resource_name = None

    def __init__(self, kernel_manager, proxy_config):
        super(CustomResourceProxy, self).__init__(kernel_manager, proxy_config)

    async def launch_process(self, kernel_cmd, **kwargs):
        kwargs['env']['KERNEL_RESOURCE_NAME'] = self.kernel_resource_name = self._determine_kernel_pod_name(**kwargs)
        kwargs['env']['KERNEL_CRD_GROUP'] = self.group
        kwargs['env']['KERNEL_CRD_VERSION'] = self.version
        kwargs['env']['KERNEL_CRD_PLURAL'] = self.plural

        await super(CustomResourceProxy, self).launch_process(kernel_cmd, **kwargs)
        return self

    def kill(self):
        result = None

        if self.kernel_resource_name:
            if self.delete_kernel_namespace and not self.kernel_manager.restarting:
                body = client.V1DeleteOptions(grace_period_seconds=0, propagation_policy='Background')
                v1_status = client.CoreV1Api().delete_namespace(name=self.kernel_namespace, body=body)

                if v1_status and v1_status.status:
                    termination_status = ['Succeeded', 'Failed', 'Terminating']
                    if any(status in v1_status.status for status in termination_status):
                        result = True
            else:
                result = self.terminate_custom_resource()

        if result:
            self.kernel_resource_name = None

        return result

    def terminate_custom_resource(self):
        try:
            delete_status = client.CustomObjectsApi().delete_cluster_custom_object(self.group, self.version,
                                                                                   self.plurals,
                                                                                   self.kernel_resource_name)

            result = delete_status and delete_status.get('status', None) == 'Success'

        except Exception as err:
            result = isinstance(err, client.rest.ApiException) and err.status == 404

        return result
