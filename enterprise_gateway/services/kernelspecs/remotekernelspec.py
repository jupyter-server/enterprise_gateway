# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel spec that knows about remote kernel types."""

from jupyter_client.kernelspec import KernelSpec, KernelSpecManager


class RemoteKernelSpecManager(KernelSpecManager):

    def _kernel_spec_class_default(self):
        return 'enterprise_gateway.services.kernelspecs.remotekernelspec.RemoteKernelSpec'


class RemoteKernelSpec(KernelSpec):
    """RemoteKernelSpec is a subclass to identify and process attributes relative to remote kernel support.
    
    """
    def __init__(self, resource_dir, **kernel_dict):
        super(RemoteKernelSpec, self).__init__(resource_dir, **kernel_dict)
        # defaults...
        self.process_proxy_class = 'enterprise_gateway.services.processproxies.processproxy.LocalProcessProxy'
        self.process_proxy_config = {}

        if 'process_proxy' in kernel_dict and kernel_dict['process_proxy']:
            self.process_proxy_class = kernel_dict['process_proxy'].get('class_name', self.process_proxy_class)
            self.process_proxy_config = kernel_dict['process_proxy'].get('config', self.process_proxy_config)

    def to_dict(self):
        d = super(RemoteKernelSpec, self).to_dict()
        d.update({'process_proxy': {'class_name': self.process_proxy_class,
                                    'config': self.process_proxy_config}})
        return d
