# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from notebook.services.kernels.kernelmanager import MappingKernelManager
import re
import sys

class SeedingMappingKernelManager(MappingKernelManager):
    @property
    def seed_kernelspec(self):
        '''
        Gets the kernel spec name required to run the seed notebook. Returns 
        None if no seed notebook exists.
        '''
        if hasattr(self, '_seed_kernelspec'):
            return self._seed_kernelspec

        if self.parent.seed_notebook:
            self._seed_kernelspec = self.parent.seed_notebook['metadata']['kernelspec']['name']
        else:
            self._seed_kernelspec = None

        return self._seed_kernelspec

    @property
    def seed_source(self):
        '''
        Gets the source of the seed notebook in cell order. Returns None if no
        seed notebook exists.
        '''
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
                        # Shutdown the kernel
                        self.shutdown_kernel(kernel_id)
                        raise RuntimeError('Error seeding kernel memory')
        return kernel_id

class APIMappingKernelManager(MappingKernelManager):
    def endpoints(self):
        '''
        Return a list of tuples containing the method+URI and the cell source
        '''
        endpoints = {}
        for cell_source in self._source:
            matched = self.api_indicator.match(cell_source)
            if matched is not None:
                uri = matched.group(2)
                verb = matched.group(1)
                if uri not in endpoints:
                    endpoints[uri] = {}
                if verb not in endpoints[uri]:
                    endpoints[uri][verb] = cell_source

        return endpoints

    def sorted_endpoints(self):
        '''Sorts the endpoints dictionary to be a list of endpoint string in order
        from most specific to least specific.
        '''
        return sorted(self.endpoints(), key=self._first_path_param_index, reverse=True)

    def _first_path_param_index(self, endpoint):
        '''Returns the index to the first path parameter for the endpoint. The
        index is not the string index, but rather where it is within the path.
        For example:
            first_path_param_index('/foo/:bar') # returns 1
            first_path_param_index('/foo/quo/:bar') # return 2
            first_path_param_index('/foo/quo/bar') # return sys.maxsize
        '''
        index = sys.maxsize
        if endpoint.find(':') >= 0:
            index = endpoint.count('/', 0, endpoint.find(':')) - 1
        return index

    @property
    def kernelspec(self):
        '''
        Gets the kernel spec name required to run the notebook. Returns
        None if no notebook exists.
        '''
        if hasattr(self, '_kernelspec'):
            return self._kernelspec

        if self.notebook:
            self._kernelspec = self.notebook['metadata']['kernelspec']['name']
        else:
            self._kernelspec = None

        return self._kernelspec

    @property
    def source(self):
        '''
        Gets the code source of the notebook in cell order. Returns None if no
        notebook exists.
        '''
        if hasattr(self, '_source'):
            return self._source

        if self.notebook:
            self._source = [
                cell['source'] for cell in self.notebook.cells
                if cell['cell_type'] == 'code'
            ]
        else:
            self._source = None

        return self._source

    def start_kernel(self, *args, **kwargs):
        '''
        Starts a kernel and then optionally executes a list of code cells on it
        before returning its ID.
        '''
        if self.kernelspec == 'r':
            self.api_indicator = re.compile('{}\s+([A-Z]+)\s+(\/.*)+'.format('#'))
        elif self.kernelspec == 'scala':
            self.api_indicator = re.compile('{}\s+([A-Z]+)\s+(\/.*)+'.format('//'))
        else:
            self.api_indicator = re.compile('{}\s+([A-Z]+)\s+(\/.*)+'.format('#'))

        kernel_id = super(MappingKernelManager, self).start_kernel(kernel_name=self.kernelspec, *args, **kwargs)
        if kernel_id and self.source is not None:
            # Only run source if the kernel matches
            kernel = self.get_kernel(kernel_id)
            if kernel.kernel_name == self.kernelspec:
                # Connect to the kernel and pump in the content of the notebook
                # before returning the kernel ID to the requesting client
                client = kernel.client()
                for code in self.source:
                        # Execute every non-API code cell and wait for each to succeed or fail
                    if self.api_indicator.match(code) is None:
                        client.execute(code)
                        msg = client.shell_channel.get_msg(block=True)
                        if msg['content']['status'] != 'ok':
                            # Shutdown the kernel
                            self.shutdown_kernel(kernel_id)
                            raise RuntimeError('Error initializing kernel memory', code)
                client.start_channels()
                client.wait_for_ready()
        return kernel_id
