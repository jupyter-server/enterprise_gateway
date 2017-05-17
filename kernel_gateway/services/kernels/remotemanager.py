# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
from ipython_genutils.importstring import import_item
from .manager import SeedingMappingKernelManager, KernelGatewayIOLoopKernelManager


class RemoteMappingKernelManager(SeedingMappingKernelManager):
    """Extends the SeedingMappingKernelManager. 

    This class is responsible for managing remote kernels. 
    """
    remote_process_proxy_class = None

    def _kernel_manager_class_default(self):
        return 'kernel_gateway.services.kernels.remotemanager.RemoteKernelManager'

    def start_kernel(self, *args, **kwargs):
        self.log.debug("RemoteMappingKernelManager.start_kernel: {}".format(kwargs['kernel_name']))
        if kwargs['kernel_name'] is not None:
            kernel_spec = self.kernel_spec_manager.get_kernel_spec(kwargs['kernel_name'])
            if self.remote_process_proxy_class is not None:
                # Detect remote type changes (when changing kernels) and reset remote
                # process proxy class if necessary.  Note, we need to keep the kernel_manager_class
                # pointing at this RemoteKernelManager.  If a local kernel is desired, this multi-kernel
                # manager will do the right thing.
                #
                if self.remote_process_proxy_class != kernel_spec.remote_process_proxy_class:
                    self.log.debug("Detected remote_process_proxy_class change from %s to %s",
                                   self.remote_process_proxy_class, kernel_spec.remote_process_proxy_class)
                    self.remote_process_proxy_class = kernel_spec.remote_process_proxy_class
                    self.log.debug("Kernel manager class is {}".format(self.kernel_manager_class))
            else:
                self.remote_process_proxy_class = kernel_spec.remote_process_proxy_class
        return super(RemoteMappingKernelManager, self).start_kernel(*args, **kwargs)


class RemoteKernelManager(KernelGatewayIOLoopKernelManager):
    """Extends the KernelGatewayIOLoopKernelManager used by the RemoteMappingKernelManager.

    This class is responsible for detecting that a remote kernel is desired, then launching the 
    appropriate class (previously pulled from the kernel spec).  The remote process 'proxy' is
    returned - upon which methods of poll(), wait(), send_signal(), and kill() can be called.
    """
    remote_process = None
#    conflicting_port = int(os.getenv('ELYRA_TEST_CONFLICTING_PORT', '0'))

    def start_kernel(self, **kw):
        if self.kernel_spec.remote_process_proxy_class is not None:
            self.log.debug("Instantiating remote kernel proxy: {}".format(self.kernel_spec.display_name))
            remote_process_class = import_item(self.kernel_spec.remote_process_proxy_class)
            self.remote_process = remote_process_class(self, **kw)

        return super(RemoteKernelManager, self).start_kernel(**kw)

    def format_kernel_cmd(self, extra_arguments=None):
        """Override for remote kernels so that we can have the kernel command built with a reference to the connection
           file (potentially) relative to the destination system, not this local system.  
        """
        if self.kernel_spec.remote_process_proxy_class is not None:
            local_connection_file = self.connection_file
            self.connection_file = self.remote_process.get_connection_filename()
            cmd = super(RemoteKernelManager, self).format_kernel_cmd(extra_arguments)
            self.log.debug("Formatted remote kernel cmd is: '{}'".format(cmd))
            self.connection_file = local_connection_file
            return cmd

        return super(RemoteKernelManager, self).format_kernel_cmd(extra_arguments)

    def _launch_kernel(self, kernel_cmd, **kw):
        if self.kernel_spec.remote_process_proxy_class is not None:
            self.log.debug("Launching remote kernel: {}".format(self.kernel_spec.display_name))
            return self.remote_process.launch_process(kernel_cmd, **kw)

        return super(RemoteKernelManager, self)._launch_kernel(kernel_cmd, **kw)

    def restart_kernel(self, now=False, **kw):
        self.reset_connections()
        super(RemoteKernelManager, self).restart_kernel(now, **kw)

    def signal_kernel(self, signum):
        """Need to override base method because it tries to send a signal to the (local)
           process group - so we bypass that code this way.
        """
        self.log.debug("RemoteKernelManager.signal_kernel({})".format(signum))

        if self.has_kernel:
            self.kernel.send_signal(signum)
        else:
            raise RuntimeError("Cannot signal kernel. No kernel is running!")

    def cleanup(self, connection_file=True):
        """Clean up resources when the kernel is shut down"""
        if self.kernel_spec.remote_process_proxy_class is not None:
            if self.has_kernel:
                self.kernel.cleanup()

        return super(RemoteKernelManager, self).cleanup(connection_file)

    def reset_connections(self):
        """Need to override and temporarily reset the ip to a local ip to avoid the check about non-local ip usage.
           The ip will be overwritten with an appropriate ip address when _launch_kernel is called and the process
           proxy is created.  In addition, since we have a higher propensity for port conflicts, assume that's the
           case for restart and reset the ports - which requires a rebuild of the connection file.
        """
        self.ip = '127.0.0.1'
        self.stdin_port = 0
        self.iopub_port = 0
        self.shell_port = 0
        self.hb_port = 0
        self.control_port = 0
        self.cleanup_connection_file()
#        self.conflicting_port = 0  - To be removed - FIXME
#
#    def testPortConflict(self):
#        if self.conflicting_port > 0:
#            self.control_port = self.conflicting_port
#            self.stdin_port = self.conflicting_port + 1
#            self.iopub_port = self.conflicting_port + 2
#            self.shell_port = self.conflicting_port + 3
#            self.hb_port = self.conflicting_port + 4
#
#    def start_kernel(self, **kw):
#        self.testPortConflict()  - To be removed - FIXME
#        super(RemoteKernelManager, self).start_kernel(**kw)
#
