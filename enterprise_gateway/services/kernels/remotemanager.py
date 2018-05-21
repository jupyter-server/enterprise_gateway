# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import sys
import signal
import re
from ipython_genutils.importstring import import_item
from kernel_gateway.services.kernels.manager import SeedingMappingKernelManager, KernelGatewayIOLoopKernelManager
from ..processproxies.processproxy import LocalProcessProxy, RemoteProcessProxy
from tornado import gen
from ipython_genutils.py3compat import (bytes_to_str, str_to_bytes)


class RemoteMappingKernelManager(SeedingMappingKernelManager):
    """Extends the SeedingMappingKernelManager.

    This class is responsible for managing remote kernels.
    """

    def _kernel_manager_class_default(self):
        return 'enterprise_gateway.services.kernels.remotemanager.RemoteKernelManager'

    @gen.coroutine
    def start_kernel(self, kernel_id=None, *args, **kwargs):
        self.log.debug("RemoteMappingKernelManager.start_kernel: {}".format(kwargs['kernel_name']))
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

        # Load connection info into member vars - no need to write out connection file
        km.load_connection_info(connection_info)

        km._launch_args = launch_args

        # Construct a process-proxy
        if km.kernel_spec.process_proxy_class:
            process_proxy_class = import_item(km.kernel_spec.process_proxy_class)
            km.process_proxy = process_proxy_class(km, proxy_config=km.kernel_spec.process_proxy_config)
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
        # Only initialize culling if available.  Warning message will be issued in gatewayapp at startup.
        func = getattr(self, 'initialize_culler', None)
        if func:
            func()
        return True


class RemoteKernelManager(KernelGatewayIOLoopKernelManager):
    """Extends the KernelGatewayIOLoopKernelManager used by the RemoteMappingKernelManager.

    This class is responsible for detecting that a remote kernel is desired, then launching the
    appropriate class (previously pulled from the kernel spec).  The process 'proxy' is
    returned - upon which methods of poll(), wait(), send_signal(), and kill() can be called.
    """
    process_proxy = None
    response_address = None
    sigint_value = None
    port_range = None

    restarting = False  # need to track whether we're in a restart situation or not

    def start_kernel(self, **kw):
        if self.kernel_spec.process_proxy_class:
            self.log.debug("Instantiating kernel '{}' with process proxy: {}".
                           format(self.kernel_spec.display_name, self.kernel_spec.process_proxy_class))
            process_proxy_class = import_item(self.kernel_spec.process_proxy_class)
            self.process_proxy = process_proxy_class(kernel_manager=self, proxy_config=self.kernel_spec.process_proxy_config)

        return super(RemoteKernelManager, self).start_kernel(**kw)

    def format_kernel_cmd(self, extra_arguments=None):
        """replace templated args (e.g. {response_address} or {port_range})"""
        cmd = super(RemoteKernelManager, self).format_kernel_cmd(extra_arguments)

        if self.response_address or self.port_range:
            ns = self._launch_args.copy()
            if self.response_address:
                ns['response_address'] = self.response_address
            if self.port_range:
                ns['port_range'] = self.port_range

            pat = re.compile(r'\{([A-Za-z0-9_]+)\}')
            def from_ns(match):
                """Get the key out of ns if it's there, otherwise no change."""
                return ns.get(match.group(1), match.group())

            return [ pat.sub(from_ns, arg) for arg in cmd ]
        return cmd

    def _launch_kernel(self, kernel_cmd, **kw):
        if self.kernel_spec.process_proxy_class:
            # Since we can't call the _launch_kernel in KernelGateway - replicate its functionality here.
            env = kw['env']
            env['KERNEL_GATEWAY'] = '1'
            if 'KG_AUTH_TOKEN' in env:
                del env['KG_AUTH_TOKEN']
            self.log.debug("Launching kernel: {} with command: {}".format(self.kernel_spec.display_name, kernel_cmd))
            return self.process_proxy.launch_process(kernel_cmd, **kw)
        # This statement shouldn't be reached since LocalProcessProxy is the default if non-existent, but just in case.
        return super(RemoteKernelManager, self)._launch_kernel(kernel_cmd, **kw)

    def request_shutdown(self, restart=False):
        super(RemoteKernelManager, self).request_shutdown(restart)

        # If we're using a remote proxy, we need to send the launcher indication that we're
        # shutting down so if can exit its listener thread, if its using one.
        if isinstance(self.process_proxy, RemoteProcessProxy):
            self.process_proxy.shutdown_listener()

    def restart_kernel(self, now=False, **kw):
        self.restarting = True
        kernel_id = os.path.basename(self.connection_file).replace('kernel-', '').replace('.json', '')
        # Check if this is a remote process proxy and if now = True. If so, check its connection count. If no
        # connections, shutdown else perform the restart.  Note: auto-restart sets now=True, but handlers use
        # the default value (False).
        if isinstance(self.process_proxy,RemoteProcessProxy) and now:
            if self.parent._kernel_connections.get(kernel_id, 0) == 0:
                self.log.warning("Remote kernel ({}) will not be automatically restarted since there are no "
                                 "clients connected at this time.".format(kernel_id))
                # Use the parent mapping kernel manager so activity monitoring and culling is also shutdown
                self.parent.shutdown_kernel(kernel_id, now=now)
                return
        super(RemoteKernelManager, self).restart_kernel(now, **kw)
        # Refresh persisted state.
        self.parent.parent.kernel_session_manager.refresh_session(kernel_id)
        self.restarting = False

    def signal_kernel(self, signum):
        """Need to override base method because it tries to send a signal to the (local)
           process group - so we bypass that code this way.
        """
        self.log.debug("RemoteKernelManager.signal_kernel({})".format(signum))
        if self.has_kernel:
            if signum == signal.SIGINT:
                if self.sigint_value is None:
                    # If we're interrupting the kernel, check if kernelspec's env defines
                    # an alternate interrupt signal.  We'll do this once per interrupted kernel.
                    self.sigint_value = signum  # use default
                    alt_sigint = self.kernel_spec.env.get('EG_ALTERNATE_SIGINT')
                    if alt_sigint:
                        try:
                            sig_value = getattr(signal, alt_sigint)
                            if type(sig_value) is int:  # Python 2
                                self.sigint_value = sig_value
                            else:  # Python 3
                                self.sigint_value = sig_value.value
                            self.log.debug(
                                "Converted EG_ALTERNATE_SIGINT '{}' to value '{}' to use as interrupt signal.".
                                format(alt_sigint, self.sigint_value))
                        except AttributeError:
                            self.log.warning("Error received when attempting to convert EG_ALTERNATE_SIGINT of "
                                             "'{}' to a value. Check kernelspec entry for kernel '{}' - using "
                                             "default 'SIGINT'".
                                             format(alt_sigint, self.kernel_spec.display_name))
                self.kernel.send_signal(self.sigint_value)
            else:
                self.kernel.send_signal(signum)
        else:
            raise RuntimeError("Cannot signal kernel. No kernel is running!")

    def cleanup(self, connection_file=True):
        """Clean up resources when the kernel is shut down"""

        # Note we must use `process_proxy` here rather than `kernel`, although they're the same value.
        # The reason is because if the kernel shutdown sequence has triggered its "forced kill" logic
        # then that method (jupyter_client/manager.py/_kill_kernel()) will set `self.kernel` to None,
        # which then prevents process proxy cleanup.
        if self.process_proxy:
            self.process_proxy.cleanup()
            self.process_proxy = None
        return super(RemoteKernelManager, self).cleanup(connection_file)

    def get_connection_info(self, session=False):
        info = super(RemoteKernelManager, self).get_connection_info(session)
        # Convert bytes to string for persistence.  Will reverse operation in load_connection_info
        info_key = info.get('key')
        if info_key:
            info['key'] = bytes_to_str(info_key)
        return info

    def load_connection_info(self, info):
        # get the key back to bytes...
        info_key = info.get('key')
        if info_key:
            info['key'] = str_to_bytes(info_key)
        return super(RemoteKernelManager, self).load_connection_info(info)

    def write_connection_file(self):
        # If this is a remote kernel that's using a response address or we're restarting, we should skip the
        # write_connection_file since it will create 5 useless ports that would not adhere to port-range
        # restrictions if configured.
        if (isinstance(self.process_proxy, LocalProcessProxy) or not self.response_address) and not self.restarting:
            # However, since we *may* want to limit the selected ports, go ahead and get the ports using
            # the process proxy (will be LocalPropcessProxy for default case) since the port selection will
            # handle the default case when the member ports aren't set anyway.
            ports = self.process_proxy.select_ports(5)
            self.shell_port=ports[0]; self.iopub_port=ports[1]; self.stdin_port=ports[2]; \
                self.hb_port=ports[3]; self.control_port=ports[4]

            return super(RemoteKernelManager, self).write_connection_file()
