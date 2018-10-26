# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel spec that knows about remote kernel types."""

import logging
from jupyter_client.kernelspec import KernelSpec, KernelSpecManager

#TODO - Remove this file once kernelspecs have been updated with metadata stanzas.

class RemoteKernelSpecManager(KernelSpecManager):

    def _kernel_spec_class_default(self):
        return 'enterprise_gateway.services.kernelspecs.remotekernelspec.RemoteKernelSpec'


class RemoteKernelSpec(KernelSpec):
    """RemoteKernelSpec is a subclass to identify and process attributes relative to remote kernel support.
    
    """
    def __init__(self, resource_dir, **kernel_dict):
        super(RemoteKernelSpec, self).__init__(resource_dir, **kernel_dict)

        # The only thing this class does now is detect malformed kernel.json files relative to a misplaced
        # process_proxy stanza.  If found, a warning message is printed and the stanza is moved into the
        # metadata dictionary.

        if 'process_proxy' in kernel_dict:
            log = logging.getLogger('EnterpriseGatewayApp')
            log.warning("WARNING! A top-level process_proxy stanza was detected for kernel '{0}'.  "
                     "Update the kernel.json file and move 'process_proxy: {{}}' within a 'metadata: {{}}' stanza.".
                     format(kernel_dict['display_name']))
            self.metadata.update({"process_proxy": kernel_dict.pop('process_proxy')})
