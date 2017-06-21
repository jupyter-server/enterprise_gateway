# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
from ipython_genutils.importstring import import_item
from .manager import SeedingMappingKernelManager, KernelGatewayIOLoopKernelManager
from tornado import gen
from ipython_genutils.py3compat import (bytes_to_str, str_to_bytes)


class RemoteMappingKernelManager(SeedingMappingKernelManager):
    """Extends the SeedingMappingKernelManager. 

    This class is responsible for managing remote kernels. 
    """
    process_proxy_class = None

    def _kernel_manager_class_default(self):
        return 'kernel_gateway.services.kernels.remotemanager.RemoteKernelManager'

    @gen.coroutine
    def start_kernel(self, kernel_id=None, *args, **kwargs):
        self.log.debug("RemoteMappingKernelManager.start_kernel: {}".format(kwargs['kernel_name']))
        if kwargs['kernel_name']:
            kernel_spec = self.kernel_spec_manager.get_kernel_spec(kwargs['kernel_name'])
            if self.process_proxy_class:
                # Detect process proxy type changes (when changing kernels) and reset remote
                # process proxy class if necessary.  Note, we need to keep the kernel_manager_class
                # pointing at this RemoteKernelManager.  If a local kernel is desired, this multi-kernel
                # manager will do the right thing.
                #
                if self.process_proxy_class != kernel_spec.process_proxy_class:
                    self.log.debug("Detected process_proxy_class change from %s to %s",
                                   self.process_proxy_class, kernel_spec.process_proxy_class)
                    self.process_proxy_class = kernel_spec.process_proxy_class
                    self.log.debug("Kernel manager class is {}".format(self.kernel_manager_class))
            else:
                self.process_proxy_class = kernel_spec.process_proxy_class
        kernel_id = yield gen.maybe_future(super(RemoteMappingKernelManager, self).start_kernel(*args, **kwargs))
        self.parent.kernel_session_manager.create_session(kernel_id, **kwargs)
        raise gen.Return(kernel_id)

    def remove_kernel(self, kernel_id):
        super(RemoteMappingKernelManager, self).remove_kernel(kernel_id)
        self.parent.kernel_session_manager.delete_session(kernel_id)

    def start_kernel_from_session(self, kernel_id, kernel_name, connection_info, process_info, launch_args):
        # Create a KernelManger instance and load connection and process info, then confirm the kernel is still
        # alive.
        constructor_kwargs = {}
        if self.kernel_spec_manager:
            constructor_kwargs['kernel_spec_manager'] = self.kernel_spec_manager

        # Construct a kernel manager...
        km = self.kernel_manager_factory(connection_file=os.path.join(
            self.connection_dir, "kernel-%s.json" % kernel_id),
            parent=self, log=self.log, kernel_name=kernel_name,
            **constructor_kwargs)

        km.load_connection_info(connection_info)
        km.write_connection_file()

        km._launch_args = launch_args

        # Construct a process-proxy
        if km.kernel_spec.process_proxy_class:
            process_proxy_class = import_item(km.kernel_spec.process_proxy_class)
            kw = {'env': {}}
            km.process_proxy = process_proxy_class(km, **kw)
            km.process_proxy.load_process_info(process_info)

            # Confirm we can even poll the process.  If not, remove the persisted session.
            if km.process_proxy.poll() is False:
                return False

        km.kernel = km.process_proxy
        km.start_restarter()
        km._connect_control_socket()
        self._kernels[kernel_id] = km
        self._kernel_connections[kernel_id] = 0
        self.start_watching_activity(kernel_id)
        self.add_restart_callback(kernel_id,
            lambda: self._handle_kernel_died(kernel_id),
            'dead',
        )
        self.initialize_culler()
        return True


class RemoteKernelManager(KernelGatewayIOLoopKernelManager):
    """Extends the KernelGatewayIOLoopKernelManager used by the RemoteMappingKernelManager.

    This class is responsible for detecting that a remote kernel is desired, then launching the 
    appropriate class (previously pulled from the kernel spec).  The process 'proxy' is
    returned - upon which methods of poll(), wait(), send_signal(), and kill() can be called.
    """
    process_proxy = None

    def start_kernel(self, **kw):
        if self.kernel_spec.process_proxy_class:
            self.log.debug("Instantiating kernel '{}' with process proxy: {}".
                           format(self.kernel_spec.display_name, self.kernel_spec.process_proxy_class))
            process_proxy_class = import_item(self.kernel_spec.process_proxy_class)
            self.process_proxy = process_proxy_class(self, **kw)
            self.ip = '0.0.0.0'  # use the zero-ip from the start, can prevent having to write out connection file again

        return super(RemoteKernelManager, self).start_kernel(**kw)

    def _launch_kernel(self, kernel_cmd, **kw):
        if self.kernel_spec.process_proxy_class:
            self.log.debug("Launching kernel: {}".format(self.kernel_spec.display_name))
            return self.process_proxy.launch_process(kernel_cmd, **kw)

        return super(RemoteKernelManager, self)._launch_kernel(kernel_cmd, **kw)

    def restart_kernel(self, now=False, **kw):
        super(RemoteKernelManager, self).restart_kernel(now, **kw)
        # Refresh persisted state.
        kernel_id = os.path.basename(self.connection_file).replace('kernel-', '').replace('.json', '')
        self.log.debug("RemoteKernelManager.restart_kernel: refreshing session for: {}".format(kernel_id))
        self.parent.parent.kernel_session_manager.refresh_session(kernel_id)

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
        if self.kernel_spec.process_proxy_class:
            if self.has_kernel:
                self.kernel.cleanup()
        return super(RemoteKernelManager, self).cleanup(connection_file)

    def get_connection_info(self, session=False):
        info = super(RemoteKernelManager, self).get_connection_info(session)
        # Convert bytes to string for persistence.  Will reverse operation in load_connection_info
        info['key'] = bytes_to_str(info['key'])
        return info

    def load_connection_info(self, info):
        # get the key back to bytes...
        info['key'] = str_to_bytes(info['key'])
        return super(RemoteKernelManager, self).load_connection_info(info)

    def write_connection_file(self):
        # Override purely for debug purposes
        self.log.debug(
            "RemoteKernelManager: Writing connection file with ip={}, control={}, hb={}, iopub={}, stdin={}, shell={}"
            .format(self.ip, self.control_port, self.hb_port, self.iopub_port, self.stdin_port, self.shell_port))
        return super(RemoteKernelManager, self).write_connection_file()
