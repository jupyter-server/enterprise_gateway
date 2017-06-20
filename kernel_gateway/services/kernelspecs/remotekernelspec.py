# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel spec that knows about remote kernel types."""

from jupyter_client.kernelspec import KernelSpec, KernelSpecManager


class RemoteKernelSpecManager(KernelSpecManager):

    def _kernel_spec_class_default(self):
        return 'kernel_gateway.services.kernelspecs.remotekernelspec.RemoteKernelSpec'


class RemoteKernelSpec(KernelSpec):
    """RemoteKernelSpec is a subclass to identify and process attributes relative to remote kernel support.
    
    """
    process_proxy_class = None

    def __init__(self, resource_dir, **kernel_dict):
        super(RemoteKernelSpec, self).__init__(resource_dir, **kernel_dict)
        if 'remote_process_proxy_class' in kernel_dict and kernel_dict['remote_process_proxy_class'] is not None:
            self.process_proxy_class = kernel_dict['remote_process_proxy_class']
        else: # ensure all kernelspecs have a process proxy entry
            self.process_proxy_class = 'kernel_gateway.services.kernels.processproxy.LocalProcessProxy'

    def to_dict(self):
        d = super(RemoteKernelSpec, self).to_dict()
        d.update({'remote_process_proxy_class': self.process_proxy_class})
        print("kernel_dict: %r" % d)
        return d
