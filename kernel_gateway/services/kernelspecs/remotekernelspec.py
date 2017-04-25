# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel spec that knows about remote kernel types."""

from jupyter_client.kernelspec import KernelSpec


class RemoteKernelSpec(KernelSpec):
    """RemoteKernelSpec is a subclass to identify and process attributes relative to remote kernel support.
    
    """
    remote_process_proxy_class = None

    def __init__(self, resource_dir, **kernel_dict):
        super(RemoteKernelSpec, self).__init__(resource_dir, **kernel_dict)
        if 'remote_process_proxy_class' in kernel_dict and kernel_dict['remote_process_proxy_class'] is not None:
            self.remote_process_proxy_class = kernel_dict['remote_process_proxy_class']

    def to_dict(self):
        d = super(RemoteKernelSpec, self).to_dict()
        d.update({'remote_process_proxy_class': self.remote_process_proxy_class})
        print("kernel_dict: %r" % d)
        return d
