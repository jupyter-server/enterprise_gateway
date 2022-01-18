# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running in docker-based containers."""

import os
import logging

from docker.client import DockerClient
from docker.errors import NotFound

from .container import ContainerProcessProxy

# Debug logging level of docker produces too much noise - raise to info by default.
logging.getLogger('urllib3.connectionpool').setLevel(os.environ.get('EG_DOCKER_LOG_LEVEL', logging.WARNING))

docker_network = os.environ.get('EG_DOCKER_NETWORK', 'bridge')

client = DockerClient.from_env()


class DockerSwarmProcessProxy(ContainerProcessProxy):
    """
    Kernel lifecycle management for kernels in Docker Swarm.
    """
    def __init__(self, kernel_manager, proxy_config):
        super(DockerSwarmProcessProxy, self).__init__(kernel_manager, proxy_config)

    def launch_process(self, kernel_cmd, **kwargs):
        """
        Launches the specified process within a Docker Swarm environment.
        """
        # Convey the network to the docker launch script
        kwargs['env']['EG_DOCKER_NETWORK'] = docker_network
        kwargs['env']['EG_DOCKER_MODE'] = 'swarm'
        return super(DockerSwarmProcessProxy, self).launch_process(kernel_cmd, **kwargs)

    def get_initial_states(self):
        """Return list of states indicating container is starting (includes running)."""
        return {'preparing', 'starting', 'running'}

    def _get_service(self):
        # Fetches the service object corresponding to the kernel with a matching label.
        service = None
        services = client.services.list(filters={'label': 'kernel_id=' + self.kernel_id})
        num_services = len(services)
        if num_services != 1:
            if num_services > 1:
                raise RuntimeError("{}: Found more than one service ({}) for kernel_id '{}'!".
                                   format(self.__class__.__name__, num_services, self.kernel_id))
        else:
            service = services[0]
            self.container_name = service.name
        return service

    def _get_task(self):
        # Fetches the task object corresponding to the service associated with the kernel.  We only ask for the
        # current task with desired-state == running.  This eliminates failed states.

        task = None
        service = self._get_service()
        if service:
            tasks = service.tasks(filters={'desired-state': 'running'})
            num_tasks = len(tasks)
            if num_tasks != 1:
                if num_tasks > 1:
                    raise RuntimeError("{}: Found more than one task ({}) for service '{}', kernel_id '{}'!".
                                       format(self.__class__.__name__, num_tasks, service.name, self.kernel_id))
            else:
                task = tasks[0]
        return task

    def get_container_status(self, iteration):
        """Return current container state."""
        # Locates the kernel container using the kernel_id filter.  If the status indicates an initial state we
        # should be able to get at the NetworksAttachments and determine the associated container's IP address.
        task_state = None
        task_id = None
        task = self._get_task()
        if task:
            task_status = task['Status']
            task_id = task['ID']
            if task_status:
                task_state = task_status['State']
                if self.assigned_host == '' and task_state == 'running':  # in self.get_initial_states():
                    # get the NetworkAttachments and pick out the first of the Network and first
                    networks_attachments = task['NetworksAttachments']
                    if len(networks_attachments) > 0:
                        address = networks_attachments[0]['Addresses'][0]
                        ip = address.split('/')[0]
                        self.assigned_ip = ip
                        self.assigned_host = self.container_name

        if iteration:  # only log if iteration is not None (otherwise poll() is too noisy)
            self.log.debug("{}: Waiting to connect to docker container. "
                           "Name: '{}', Status: '{}', IPAddress: '{}', KernelID: '{}', TaskID: '{}'".
                           format(iteration, self.container_name, task_state,
                                  self.assigned_ip, self.kernel_id, task_id))
        return task_state

    def terminate_container_resources(self):
        """Terminate any artifacts created on behalf of the container's lifetime."""
        # Remove the docker service.

        result = True  # We'll be optimistic
        service = self._get_service()
        if service:
            try:
                service.remove()  # Service still exists, attempt removal
            except Exception as err:
                self.log.debug("{} Termination of service: {} raised exception: {}".
                               format(self.__class__.__name__, service.name, err))
                if isinstance(err, NotFound):
                    pass  # okay if its not found
                else:
                    result = False
                    self.log.warning("Error occurred removing service: {}".format(err))
        if result:
            self.log.debug("{}.terminate_container_resources, service {}, kernel ID: {} has been terminated.".
                           format(self.__class__.__name__, self.container_name, self.kernel_id))
            self.container_name = None
            result = None  # maintain jupyter contract
        else:
            self.log.warning("{}.terminate_container_resources, container {}, kernel ID: {} has not been terminated.".
                             format(self.__class__.__name__, self.container_name, self.kernel_id))
        return result


class DockerProcessProxy(ContainerProcessProxy):
    """Kernel lifecycle management for Docker kernels (non-Swarm)."""
    def __init__(self, kernel_manager, proxy_config):
        super(DockerProcessProxy, self).__init__(kernel_manager, proxy_config)

    def launch_process(self, kernel_cmd, **kwargs):
        """Launches the specified process within a Docker environment."""
        # Convey the network to the docker launch script
        kwargs['env']['EG_DOCKER_NETWORK'] = docker_network
        kwargs['env']['EG_DOCKER_MODE'] = 'docker'
        return super(DockerProcessProxy, self).launch_process(kernel_cmd, **kwargs)

    def get_initial_states(self):
        """Return list of states indicating container is starting (includes running)."""
        return {'created', 'running'}

    def _get_container(self):
        # Fetches the container object corresponding the the kernel_id label.
        # Only used when docker mode == regular (not swarm)

        container = None
        containers = client.containers.list(filters={'label': 'kernel_id=' + self.kernel_id})
        num_containers = len(containers)
        if num_containers != 1:
            if num_containers > 1:
                raise RuntimeError("{}: Found more than one container ({}) for kernel_id '{}'!".
                                   format(self.__class__.__name__, num_containers, self.kernel_id))
        else:
            container = containers[0]
        return container

    def get_container_status(self, iteration):
        """Return current container state."""
        # Locates the kernel container using the kernel_id filter.  If the phase indicates Running, the pod's IP
        # is used for the assigned_ip.  Only used when docker mode == regular (non swarm)
        container_status = None

        container = self._get_container()
        if container:
            self.container_name = container.name
            if container.status:
                container_status = container.status
                if container_status == 'running' and self.assigned_host == '':
                    # Container is running, capture IP

                    # we'll use this as a fallback in case we don't find our network
                    self.assigned_ip = container.attrs.get('NetworkSettings').get('IPAddress')
                    networks = container.attrs.get('NetworkSettings').get('Networks')
                    if len(networks) > 0:
                        self.assigned_ip = networks.get(docker_network).get('IPAddress')
                        self.log.debug("Using assigned_ip {} from docker network '{}'.".
                                       format(self.assigned_ip, docker_network))
                    else:
                        self.log.warning("Docker network '{}' could not be located in container attributes - "
                                         "using assigned_ip '{}'.".format(docker_network, self.assigned_ip))

                    self.assigned_host = self.container_name

        if iteration:  # only log if iteration is not None (otherwise poll() is too noisy)
            self.log.debug("{}: Waiting to connect to docker container. "
                           "Name: '{}', Status: '{}', IPAddress: '{}', KernelID: '{}'".
                           format(iteration, self.container_name, container_status, self.assigned_ip, self.kernel_id))

        return container_status

    def terminate_container_resources(self):
        """Terminate any artifacts created on behalf of the container's lifetime."""
        # Remove the container

        result = True  # Since we run containers with remove=True, we'll be optimistic
        container = self._get_container()
        if container:
            try:
                container.remove(force=True)  # Container still exists, attempt forced removal
            except Exception as err:
                self.log.debug("Container termination for container: {} raised exception: {}".
                               format(container.name, err))
                if isinstance(err, NotFound):
                    pass  # okay if its not found
                else:
                    result = False
                    self.log.warning("Error occurred removing container: {}".format(err))

        if result:
            self.log.debug("{}.terminate_container_resources, container {}, kernel ID: {} has been terminated.".
                           format(self.__class__.__name__, self.container_name, self.kernel_id))
            self.container_name = None
            result = None  # maintain jupyter contract
        else:
            self.log.warning("{}.terminate_container_resources, container {}, kernel ID: {} has not been terminated.".
                             format(self.__class__.__name__, self.container_name, self.kernel_id))
        return result
