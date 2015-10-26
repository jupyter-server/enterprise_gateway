# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from notebook.services.kernels.kernelmanager import MappingKernelManager

class SeedingMappingKernelManager(MappingKernelManager):
    def start_kernel(self, *args, **kwargs):
        '''
        Starts a kernel and then optionally executes a list of code cells on it
        before returning its ID.
        '''
        kernel_id = super(MappingKernelManager, self).start_kernel(*args, **kwargs)

        seed_source = self.parent.seed_source

        # Connect to the kernel and pump in the content of the notebook
        # before returning the kernel ID to the requesting client
        if seed_source is not None and kernel_id:
            # Get a client for the new kernel
            kernel = self.get_kernel(kernel_id)
            client = kernel.client()
            for code in seed_source:
                # Execute every code cell and wait for each to succeed or fail
                client.execute(code)
                msg = client.shell_channel.get_msg(block=True)
                if msg['content']['status'] != 'ok':
                    raise RuntimeError(msg)
        return kernel_id
