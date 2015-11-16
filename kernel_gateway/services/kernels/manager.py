# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from notebook.services.kernels.kernelmanager import MappingKernelManager

class SeedingMappingKernelManager(MappingKernelManager):
    @property
    def seed_kernelspec(self):
        if hasattr(self, '_seed_kernelspace'):
            return self._seed_kernelspace

        if self.parent.seed_notebook:
            self._seed_kernelspace = self.parent.seed_notebook['metadata']['kernelspec']['name']
        else:
            self._seed_kernelspace = None

        return self._seed_kernelspace

    @property
    def seed_source(self):
        if hasattr(self, '_seed_source'):
            return self._seed_source

        if self.parent.seed_notebook:
            self._seed_source = [
                cell['source'] for cell in self.parent.seed_notebook.cells 
                if cell['cell_type'] == 'code'
            ]
        else:
            self._seed_source = None

        return self._seed_source


    def start_kernel(self, *args, **kwargs):
        '''
        Starts a kernel and then optionally executes a list of code cells on it
        before returning its ID.
        '''
        kernel_id = super(MappingKernelManager, self).start_kernel(*args, **kwargs)

        if kernel_id and self.seed_source is not None:
            # Only run source if the kernel matches
            kernel = self.get_kernel(kernel_id)
            if kernel.kernel_name == self.seed_kernelspec:
                # Connect to the kernel and pump in the content of the notebook
                # before returning the kernel ID to the requesting client
                client = kernel.client()
                for code in self.seed_source:
                    # Execute every code cell and wait for each to succeed or fail
                    client.execute(code)
                    msg = client.shell_channel.get_msg(block=True)
                    if msg['content']['status'] != 'ok':
                        raise RuntimeError('Error seeding kernel memory')
        return kernel_id
