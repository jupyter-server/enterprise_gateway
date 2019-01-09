# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running in containers."""

import os
import signal
import abc

import urllib3  # docker ends up using this and it causes lots of noise, so turn off warnings

from jupyter_client import launch_kernel, localinterfaces

from .processproxy import RemoteProcessProxy

urllib3.disable_warnings()

local_ip = localinterfaces.public_ips()[0]


class ContainerProcessProxy(RemoteProcessProxy):
    """Kernel lifecycle management for container-based kernels."""
    def __init__(self, kernel_manager, proxy_config):
        super(ContainerProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.container_name = ''
        self.assigned_node_ip = None
        self._determine_kernel_images(proxy_config)

    def _determine_kernel_images(self, proxy_config):
        """Determine which kernel images to use.

        Initialize to any defined in the process proxy override that then let those provided
        by client via env override.
        """
        if proxy_config.get('image_name'):
            self.kernel_image = proxy_config.get('image_name')
        self.kernel_image = os.environ.get('KERNEL_IMAGE', self.kernel_image)

        self.kernel_executor_image = self.kernel_image  # Default the executor image to current image
        if proxy_config.get('executor_image_name'):
            self.kernel_executor_image = proxy_config.get('executor_image_name')
        self.kernel_executor_image = os.environ.get('KERNEL_EXECUTOR_IMAGE', self.kernel_executor_image)

    def launch_process(self, kernel_cmd, **kwargs):
        """Launches the specified process within the container environment."""
        # Set env before superclass call so we see these in the debug output

        kwargs['env']['KERNEL_IMAGE'] = self.kernel_image
        kwargs['env']['KERNEL_EXECUTOR_IMAGE'] = self.kernel_executor_image

        super(ContainerProcessProxy, self).launch_process(kernel_cmd, **kwargs)

        self.local_proc = launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info("{}: kernel launched. Kernel image: {}, KernelID: {}, cmd: '{}'"
                      .format(self.__class__.__name__, self.kernel_image, self.kernel_id, kernel_cmd))

        self.confirm_remote_startup()

        return self

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
        if container_status is None or container_status in self.get_initial_states():
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

    def confirm_remote_startup(self):
        """Confirms the container has started and returned necessary connection information."""
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            self.handle_timeout()

            container_status = self.get_container_status(str(i))
            if container_status:
                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()
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
