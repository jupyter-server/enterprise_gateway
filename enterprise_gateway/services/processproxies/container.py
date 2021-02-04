# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running in containers."""

import abc
import os
import signal
import urllib3  # docker ends up using this and it causes lots of noise, so turn off warnings

from jupyter_client import localinterfaces

from .processproxy import RemoteProcessProxy

urllib3.disable_warnings()

local_ip = localinterfaces.public_ips()[0]

default_kernel_uid = '1000'  # jovyan user is the default
default_kernel_gid = '100'  # users group is the default

# These could be enforced via a PodSecurityPolicy, but those affect
# all pods so the cluster admin would need to configure those for
# all applications.
prohibited_uids = os.getenv("EG_PROHIBITED_UIDS", "0").split(',')
prohibited_gids = os.getenv("EG_PROHIBITED_GIDS", "0").split(',')

mirror_working_dirs = bool((os.getenv('EG_MIRROR_WORKING_DIRS', 'false').lower() == 'true'))

# Get the globally-configured default images.  Defaulting to None if not set.
default_kernel_image = os.getenv('EG_KERNEL_IMAGE')
default_kernel_executor_image = os.getenv('EG_KERNEL_EXECUTOR_IMAGE')


class ContainerProcessProxy(RemoteProcessProxy):
    """
    Kernel lifecycle management for container-based kernels.
    """
    def __init__(self, kernel_manager, proxy_config):
        super(ContainerProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.container_name = ''
        self.assigned_node_ip = None

    def _determine_kernel_images(self, **kwargs):
        """
        Determine which kernel images to use.

        Initialize to any defined in the process proxy override that then let those provided
        by client via env override.
        """
        kernel_image = self.proxy_config.get('image_name', default_kernel_image)
        self.kernel_image = kwargs['env'].get('KERNEL_IMAGE', kernel_image)

        if self.kernel_image is None:
            self.log_and_raise(http_status_code=500,
                               reason="No kernel image could be determined! Set the `image_name` in the "
                                      "process_proxy.config stanza of the corresponding kernel.json file.")

        # If no default executor image is configured, default it to current image
        kernel_executor_image = self.proxy_config.get('executor_image_name',
                                                      default_kernel_executor_image or self.kernel_image)
        self.kernel_executor_image = kwargs['env'].get('KERNEL_EXECUTOR_IMAGE', kernel_executor_image)

    async def launch_process(self, kernel_cmd, **kwargs):
        """
        Launches the specified process within the container environment.
        """
        # Set env before superclass call so we see these in the debug output

        self._determine_kernel_images(**kwargs)
        kwargs['env']['KERNEL_IMAGE'] = self.kernel_image
        kwargs['env']['KERNEL_EXECUTOR_IMAGE'] = self.kernel_executor_image

        if not mirror_working_dirs:  # If mirroring is not enabled, remove working directory if present
            if 'KERNEL_WORKING_DIR' in kwargs['env']:
                del kwargs['env']['KERNEL_WORKING_DIR']

        self._enforce_prohibited_ids(**kwargs)

        await super(ContainerProcessProxy, self).launch_process(kernel_cmd, **kwargs)

        self.local_proc = self.launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info("{}: kernel launched. Kernel image: {}, KernelID: {}, cmd: '{}'"
                      .format(self.__class__.__name__, self.kernel_image, self.kernel_id, kernel_cmd))

        await self.confirm_remote_startup()
        return self

    def _enforce_prohibited_ids(self, **kwargs):
        """Determine UID and GID with which to launch container and ensure they are not prohibited."""
        kernel_uid = kwargs['env'].get('KERNEL_UID', default_kernel_uid)
        kernel_gid = kwargs['env'].get('KERNEL_GID', default_kernel_gid)

        if kernel_uid in prohibited_uids:
            http_status_code = 403
            error_message = "Kernel's UID value of '{}' has been denied via EG_PROHIBITED_UIDS!".format(kernel_uid)
            self.log_and_raise(http_status_code=http_status_code, reason=error_message)
        elif kernel_gid in prohibited_gids:
            http_status_code = 403
            error_message = "Kernel's GID value of '{}' has been denied via EG_PROHIBITED_GIDS!".format(kernel_gid)
            self.log_and_raise(http_status_code=http_status_code, reason=error_message)

        # Ensure the kernel's env has what it needs in case they came from defaults
        kwargs['env']['KERNEL_UID'] = kernel_uid
        kwargs['env']['KERNEL_GID'] = kernel_gid

    def poll(self):
        """Determines if container is still active.

        Submitting a new kernel to the container manager will take a while to be Running.
        Thus kernel ID will probably not be available immediately for poll.
        So will regard the container as active when no status is available or one of the initial
        phases.

        Returns
        -------
        None if the container cannot be found or its in an initial state. Otherwise False.
        """
        result = False

        container_status = self.get_container_status(None)
        # Do not check whether container_status is None
        # EG couldn't restart kernels although connections exists.
        # See https://github.com/jupyter/enterprise_gateway/issues/827
        if container_status in self.get_initial_states():
            result = None

        return result

    def send_signal(self, signum):
        """Send signal `signum` to container.

        Parameters
        ----------
        signum : int
            The signal number to send.  Zero is used to determine heartbeat.
        """
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            # This is very likely an interrupt signal, so defer to the super class
            # which should use the communication port.
            return super(ContainerProcessProxy, self).send_signal(signum)

    def kill(self):
        """Kills a containerized kernel.

        Returns
        -------
        None if the container is gracefully terminated, False otherwise.
        """
        result = None

        if self.container_name:  # We only have something to terminate if we have a name
            result = self.terminate_container_resources()

        return result

    def cleanup(self):
        # Since container objects don't necessarily go away on their own, we need to perform the same
        # cleanup we'd normally perform on forced kill situations.

        self.kill()
        super(ContainerProcessProxy, self).cleanup()

    async def confirm_remote_startup(self):
        """Confirms the container has started and returned necessary connection information."""
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            await self.handle_timeout()

            container_status = self.get_container_status(str(i))
            if container_status:
                if self.assigned_host != '':
                    ready_to_connect = await self.receive_connection_info()
                    self.pid = 0  # We won't send process signals for kubernetes lifecycle management
                    self.pgid = 0
            else:
                self.detect_launch_failure()

    def get_process_info(self):
        """Captures the base information necessary for kernel persistence relative to containers."""
        process_info = super(ContainerProcessProxy, self).get_process_info()
        process_info.update({'assigned_node_ip': self.assigned_node_ip, })
        return process_info

    def load_process_info(self, process_info):
        """Loads the base information necessary for kernel persistence relative to containers."""
        super(ContainerProcessProxy, self).load_process_info(process_info)
        self.assigned_node_ip = process_info['assigned_node_ip']

    @abc.abstractmethod
    def get_initial_states(self):
        """Return list of states indicating container is starting (includes running)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_container_status(self, iteration_string):
        """Return current container state."""
        raise NotImplementedError

    @abc.abstractmethod
    def terminate_container_resources(self):
        """Terminate any artifacts created on behalf of the container's lifetime."""
        raise NotImplementedError
