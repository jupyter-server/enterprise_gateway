# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import signal
import re
import uuid

from tornado import gen
from ipython_genutils.py3compat import unicode_type
from ipython_genutils.importstring import import_item
from kernel_gateway.services.kernels.manager import SeedingMappingKernelManager, KernelGatewayIOLoopKernelManager

from ..processproxies.processproxy import LocalProcessProxy, RemoteProcessProxy
from ..sessions.kernelsessionmanager import KernelSessionManager


def get_process_proxy_config(kernelspec):
    """Return the process-proxy stanza from the kernelspec.

    Checks the kernelspec's metadata dictionary for a process proxy entry.
    If found, it is returned, else one is created relative to the LocalProcessProxy and returns.

    Parameters
    ----------
    kernelspec : obj
        The kernel specification object from which the process-proxy dictionary is derived.

    Returns
    -------
    process_proxy : dict
        The process proxy portion of the kernelspec.  If one does not exist, it will contain the default
        information.  If no `config` sub-dictionary exists, an empty `config` dictionary will be present.

    """
    if 'process_proxy' in kernelspec.metadata:
        process_proxy = kernelspec.metadata.get('process_proxy')
        if 'class_name' in process_proxy:  # If no class_name, return default
                if 'config' not in process_proxy:  # if class_name, but no config stanza, add one
                    process_proxy.update({"config": {}})
                return process_proxy  # Return what we found (plus config stanza if necessary)
    return {"class_name": "enterprise_gateway.services.processproxies.processproxy.LocalProcessProxy", "config": {}}


class RemoteMappingKernelManager(SeedingMappingKernelManager):
    """Extends the SeedingMappingKernelManager with support for managing remote kernels via the process-proxy. """
    def _kernel_manager_class_default(self):
        return 'enterprise_gateway.services.kernels.remotemanager.RemoteKernelManager'

    @gen.coroutine
    def start_kernel(self, *args, **kwargs):
        """Starts a kernel for a session and return its kernel_id.

        Returns
        -------
        kernel_id : str
            The uuid associated with the new kernel.  This string will equal the value
            of the input parameter `kernel_id` if one was provided.
        """
        username = KernelSessionManager.get_kernel_username(**kwargs)
        self.log.debug("RemoteMappingKernelManager.start_kernel: {kernel_name}, kernel_username: {username}".
                       format(kernel_name=kwargs['kernel_name'], username=username))
        kernel_id = yield gen.maybe_future(super(RemoteMappingKernelManager, self).start_kernel(*args, **kwargs))
        self.parent.kernel_session_manager.create_session(kernel_id, **kwargs)
        raise gen.Return(kernel_id)

    def remove_kernel(self, kernel_id):
        """ Removes the kernel associated with `kernel_id` from the internal map and deletes the kernel session. """
        super(RemoteMappingKernelManager, self).remove_kernel(kernel_id)
        self.parent.kernel_session_manager.delete_session(kernel_id)

    def start_kernel_from_session(self, kernel_id, kernel_name, connection_info, process_info, launch_args):
        """ Starts a kernel from a persisted kernel session.

        This method is used in HA situations when a previously running Enterprise Gateway instance has
        terminated and a new instance - with access to the persisted kernel sessions is starting up.
        It attempts to "revive" the persisted kernel session by instantiating the necessary class instances
        to re-establish communication with the currently active kernel.

        Note that this method is typically only successful when kernel instances are remote from the
        previously running Enterprise Gateway server - since the need to re-establish communications
        won't work if the kernels were also local to the (probably) terminated server.

        Parameters
        ----------
        kernel_id : str
            The uuid string corresponding to the kernel to start

        kernel_name : str
            The name of kernel to start

        connection_info : dict
            The connection information for the kernel loaded from persistent storage

        process_info : dict
            The process information corresponding to the process-proxy used by the kernel and loaded
            from persistent storage

        launch_args : dict
            The arguments used for the initial launch of the kernel

        Returns
        -------
            True if kernel could be located and started, False otherwise.

        """
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
        process_proxy = get_process_proxy_config(km.kernel_spec)
        process_proxy_class = import_item(process_proxy.get('class_name'))
        km.process_proxy = process_proxy_class(km, proxy_config=process_proxy.get('config'))
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
                                  'dead',)
        # Only initialize culling if available.  Warning message will be issued in gatewayapp at startup.
        func = getattr(self, 'initialize_culler', None)
        if func:
            func()
        return True

    def new_kernel_id(self, **kwargs):
        """Determines the kernel_id to use for a new kernel.

        This method provides a mechanism by which clients can specify a kernel's id.  In this case
        that mechanism is via the per-kernel environment variable: KERNEL_ID.  If specified, its value
        will be validated and returned, otherwise the result from the superclass method is returned.

        NOTE: This method exists in jupyter_client.multikernelmanager.py for releases > 5.2.3.  If you
        find that this method is not getting invoked, then you likely need to update the version of
        jupyter_client.  The Enterprise Gateway dependency will be updated once new releases of
        jupyter_client are more prevalent.

        Returns
        -------
        kernel_id : str
            The uuid string to associate with the new kernel
        """
        env = kwargs.get('env')
        if env and env.get('KERNEL_ID'):   # If there's a KERNEL_ID in the env, check it out
            # convert string back to UUID - validating string in the process.
            str_kernel_id = env.get('KERNEL_ID')
            try:
                str_v4_kernel_id = str(uuid.UUID(str_kernel_id, version=4))
                if str_kernel_id != str_v4_kernel_id:  # Given string is not uuid v4 compliant
                    raise ValueError("value is not uuid v4 compliant")
            except ValueError as ve:
                self.log.error("Invalid v4 UUID value detected in ['env']['KERNEL_ID']: '{}'!  Error: {}".
                               format(str_kernel_id, ve))
                raise ve
            # user-provided id is valid, use it
            kernel_id = unicode_type(str_kernel_id)
            self.log.debug("Using user-provided kernel_id: {}".format(kernel_id))
        else:
            kernel_id = super(RemoteMappingKernelManager, self).new_kernel_id(**kwargs)

        return kernel_id


class RemoteKernelManager(KernelGatewayIOLoopKernelManager):
    """Extends the KernelGatewayIOLoopKernelManager used by the RemoteMappingKernelManager.

    This class is responsible for detecting that a remote kernel is desired, then launching the
    appropriate class (previously pulled from the kernel spec).  The process 'proxy' is
    returned - upon which methods of poll(), wait(), send_signal(), and kill() can be called.
    """

    def __init__(self, **kwargs):
        super(KernelGatewayIOLoopKernelManager, self).__init__(**kwargs)
        self.process_proxy = None
        self.response_address = None
        self.sigint_value = None
        self.port_range = None
        self.kernel_id = None
        self.user_overrides = {}
        self.restarting = False  # need to track whether we're in a restart situation or not

    def start_kernel(self, **kwargs):
        """Starts a kernel in a separate process.

        Where the started kernel resides depends on the configured process proxy.

        Parameters
        ----------
        `**kwargs` : optional
             keyword arguments that are passed down to build the kernel_cmd
             and launching the kernel (e.g. Popen kwargs).
        """

        process_proxy = get_process_proxy_config(self.kernel_spec)
        process_proxy_class_name = process_proxy.get('class_name')
        self.log.debug("Instantiating kernel '{}' with process proxy: {}".
                       format(self.kernel_spec.display_name, process_proxy_class_name))
        process_proxy_class = import_item(process_proxy_class_name)
        self.process_proxy = process_proxy_class(kernel_manager=self, proxy_config=process_proxy.get('config'))
        self._capture_user_overrides(**kwargs)
        super(RemoteKernelManager, self).start_kernel(**kwargs)

    def _capture_user_overrides(self, **kwargs):
        """
           Make a copy of any whitelist or KERNEL_ env values provided by user.  These will be injected
           back into the env after the kernelspec env has been applied.  This enables defaulting behavior
           of the kernelspec env stanza that would have otherwise overridden the user-provided values.
        """
        env = kwargs.get('env', {})
        self.user_overrides.update({key: value for key, value in env.items()
                    if key.startswith('KERNEL_') or
                                    key in self.parent.parent.env_process_whitelist or
                                    key in self.parent.parent.personality.env_whitelist})

    def format_kernel_cmd(self, extra_arguments=None):
        """ Replace templated args (e.g. {response_address}, {port_range}, or {kernel_id}). """
        cmd = super(RemoteKernelManager, self).format_kernel_cmd(extra_arguments)

        if self.response_address or self.port_range or self.kernel_id:
            ns = self._launch_args.copy()
            if self.response_address:
                ns['response_address'] = self.response_address
            if self.port_range:
                ns['port_range'] = self.port_range
            if self.kernel_id:
                ns['kernel_id'] = self.kernel_id

            pat = re.compile(r'\{([A-Za-z0-9_]+)\}')

            def from_ns(match):
                """Get the key out of ns if it's there, otherwise no change."""
                return ns.get(match.group(1), match.group())

            return [pat.sub(from_ns, arg) for arg in cmd]
        return cmd

    def _launch_kernel(self, kernel_cmd, **kwargs):
        # Note: despite the under-bar prefix to this method, the jupyter_client comment says that
        # this method should be "[overridden] in a subclass to launch kernel subprocesses differently".
        # So that's what we've done.

        env = kwargs['env']

        # Apply user_overrides to enable defaulting behavior from kernelspec.env stanza.  Note that we do this
        # BEFORE setting KERNEL_GATEWAY and removing KG_AUTH_TOKEN so those operations cannot be overridden.
        env.update(self.user_overrides)

        # Since we can't call the _launch_kernel in KernelGateway - replicate its functionality here.
        env['KERNEL_GATEWAY'] = '1'
        if 'KG_AUTH_TOKEN' in env:
            del env['KG_AUTH_TOKEN']

        self.log.debug("Launching kernel: {} with command: {}".format(self.kernel_spec.display_name, kernel_cmd))
        return self.process_proxy.launch_process(kernel_cmd, **kwargs)

    def request_shutdown(self, restart=False):
        """ Send a shutdown request via control channel and process proxy (if remote). """
        super(RemoteKernelManager, self).request_shutdown(restart)

        # If we're using a remote proxy, we need to send the launcher indication that we're
        # shutting down so it can exit its listener thread, if its using one.
        if isinstance(self.process_proxy, RemoteProcessProxy):
            self.process_proxy.shutdown_listener()

    def restart_kernel(self, now=False, **kwargs):
        """Restarts a kernel with the arguments that were used to launch it.

        This is an automatic restart request (now=True) AND this is associated with a
        remote kernel, check the active connection count.  If there are zero connections, do
        not restart the kernel.

        Parameters
        ----------
        now : bool, optional
            If True, the kernel is forcefully restarted *immediately*, without
            having a chance to do any cleanup action.  Otherwise the kernel is
            given 1s to clean up before a forceful restart is issued.

            In all cases the kernel is restarted, the only difference is whether
            it is given a chance to perform a clean shutdown or not.

        `**kwargs` : optional
            Any options specified here will overwrite those used to launch the
            kernel.
        """
        self.restarting = True
        kernel_id = os.path.basename(self.connection_file).replace('kernel-', '').replace('.json', '')
        # Check if this is a remote process proxy and if now = True. If so, check its connection count. If no
        # connections, shutdown else perform the restart.  Note: auto-restart sets now=True, but handlers use
        # the default value (False).
        if isinstance(self.process_proxy, RemoteProcessProxy) and now:
            if self.parent._kernel_connections.get(kernel_id, 0) == 0:
                self.log.warning("Remote kernel ({}) will not be automatically restarted since there are no "
                                 "clients connected at this time.".format(kernel_id))
                # Use the parent mapping kernel manager so activity monitoring and culling is also shutdown
                self.parent.shutdown_kernel(kernel_id, now=now)
                return
        super(RemoteKernelManager, self).restart_kernel(now, **kwargs)
        if isinstance(self.process_proxy, RemoteProcessProxy):  # for remote kernels...
            # Re-establish activity watching...
            if self._activity_stream:
                self._activity_stream.close()
                self._activity_stream = None
            self.parent.start_watching_activity(kernel_id)
        # Refresh persisted state.
        self.parent.parent.kernel_session_manager.refresh_session(kernel_id)
        self.restarting = False

    def signal_kernel(self, signum):
        """Sends signal `signum` to the kernel process. """
        self.log.debug("RemoteKernelManager.signal_kernel({})".format(signum))
        if self.has_kernel:
            if signum == signal.SIGINT:
                if self.sigint_value is None:
                    # If we're interrupting the kernel, check if kernelspec's env defines
                    # an alternate interrupt signal.  We'll do this once per interrupted kernel.
                    # This is required for kernels whose language may prevent signals across
                    # process/user boundaries (Scala, for example).
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

    def write_connection_file(self):
        """Write connection info to JSON dict in self.connection_file if the kernel is local.

        If this is a remote kernel that's using a response address or we're restarting, we should skip the
        write_connection_file since it will create 5 useless ports that would not adhere to port-range
        restrictions if configured.
        """
        if (isinstance(self.process_proxy, LocalProcessProxy) or not self.response_address) and not self.restarting:
            # However, since we *may* want to limit the selected ports, go ahead and get the ports using
            # the process proxy (will be LocalPropcessProxy for default case) since the port selection will
            # handle the default case when the member ports aren't set anyway.
            ports = self.process_proxy.select_ports(5)
            self.shell_port = ports[0]
            self.iopub_port = ports[1]
            self.stdin_port = ports[2]
            self.hb_port = ports[3]
            self.control_port = ports[4]

            return super(RemoteKernelManager, self).write_connection_file()
