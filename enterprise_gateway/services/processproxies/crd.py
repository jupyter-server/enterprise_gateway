# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running based on k8s custom resource."""

import abc
import signal
import urllib3  # docker ends up using this and it causes lots of noise, so turn off warnings

from jupyter_client import localinterfaces

from .processproxy import RemoteProcessProxy
from kubernetes import config, client

urllib3.disable_warnings()
local_ip = localinterfaces.public_ips()[0]
config.load_incluster_config()


class CustomResourceProxy(RemoteProcessProxy):
    group = version = plural = None
    custom_resource_template_name = None
    kernel_resource_name = None

    def __init__(self, kernel_manager, proxy_config):
        super(CustomResourceProxy, self).__init__(kernel_manager, proxy_config)
        self.assigned_node_ip = None

    async def launch_process(self, kernel_cmd, **kwargs):
        kwargs['env']['KERNEL_CRD_NAME'] = self.kernel_resource_name
        kwargs['env']['KERNEL_CRD_GROUP'] = self.group
        kwargs['env']['KERNEL_CRD_VERSION'] = self.version
        kwargs['env']['KERNEL_CRD_PLURAL'] = self.plural

        await super(CustomResourceProxy, self).launch_process(kernel_cmd, **kwargs)

        self.local_proc = self.launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.info("{}: kernel launched. KernelID: {}, cmd: '{}'"
                      .format(self.__class__.__name__, self.kernel_id, kernel_cmd))

        await self.confirm_remote_startup()
        return self

    def poll(self):
        result = False

        resource_status = self.get_resource_status(None)

        if resource_status in self.get_initial_states():
            result = None

        return result

    def send_signal(self, signum):
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            return super(CustomResourceProxy, self).send_signal(signum)

    def kill(self):
        result = None

        if self.kernel_resource_name:
            result = self.terminate_custom_resource()

        return result

    def cleanup(self):
        # Since container objects don't necessarily go away on their own, we need to perform the same
        # cleanup we'd normally perform on forced kill situations.

        self.kill()
        super(CustomResourceProxy, self).cleanup()

    async def confirm_remote_startup(self):
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            await self.handle_timeout()

            resource_status = self.get_resource_status(str(i))
            if resource_status and self.assigned_host != '':
                ready_to_connect = await self.receive_connection_info()
                self.pid = self.pgid = 0  # We won't send process signals for kubernetes lifecycle management
            else:
                self.detect_launch_failure()

    def get_process_info(self):
        process_info = super(CustomResourceProxy, self).get_process_info()
        process_info.update({'assigned_node_ip': self.assigned_node_ip, })
        return process_info

    def load_process_info(self, process_info):
        super(CustomResourceProxy, self).load_process_info(process_info)
        self.assigned_node_ip = process_info['assigned_node_ip']

    @abc.abstractmethod
    def get_initial_states(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_resource_status(self, iteration):
        raise NotImplementedError

    def terminate_custom_resource(self):
        try:
            delete_status = client.CustomObjectsApi().delete_cluster_custom_object(self.group, self.version,
                                                                                   self.plurals,
                                                                                   self.kernel_resource_name)

            result = delete_status and delete_status.get('status', None) == 'Success'

        except Exception as err:
            result = isinstance(err, client.rest.ApiException) and err.status == 404

        return result
