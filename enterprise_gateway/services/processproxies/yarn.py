# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running in YARN clusters."""

import asyncio
import errno
import logging
import os
import signal
import socket
import time

from jupyter_client import launch_kernel, localinterfaces
from yarn_api_client.resource_manager import ResourceManager

from .processproxy import RemoteProcessProxy

# Default logging level of yarn-api and underlying connectionpool produce too much noise - raise to warning only.
logging.getLogger('yarn_api_client').setLevel(os.getenv('EG_YARN_LOG_LEVEL', logging.WARNING))
logging.getLogger('urllib3.connectionpool').setLevel(os.environ.get('EG_YARN_LOG_LEVEL', logging.WARNING))

local_ip = localinterfaces.public_ips()[0]
poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
max_poll_attempts = int(os.getenv('EG_MAX_POLL_ATTEMPTS', '10'))
yarn_shutdown_wait_time = float(os.getenv('EG_YARN_SHUTDOWN_WAIT_TIME', '15.0'))


class YarnClusterProcessProxy(RemoteProcessProxy):
    """Kernel lifecycle management for YARN clusters."""
    initial_states = {'NEW', 'SUBMITTED', 'ACCEPTED', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED', 'FAILED'}

    def __init__(self, kernel_manager, proxy_config):
        super(YarnClusterProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.application_id = None
        self.last_known_state = None
        self.candidate_queue = None
        self.candidate_partition = None
        self.local_proc = None
        self.pid = None
        self.ip = None

        self.yarn_endpoint \
            = proxy_config.get('yarn_endpoint',
                               kernel_manager.yarn_endpoint)
        self.alt_yarn_endpoint \
            = proxy_config.get('alt_yarn_endpoint',
                               kernel_manager.alt_yarn_endpoint)

        self.yarn_endpoint_security_enabled \
            = proxy_config.get('yarn_endpoint_security_enabled',
                               kernel_manager.yarn_endpoint_security_enabled)

        endpoints = None
        if self.yarn_endpoint:
            endpoints = [self.yarn_endpoint]

            # Only check alternate if "primary" is set.
            if self.alt_yarn_endpoint:
                endpoints.append(self.alt_yarn_endpoint)

        auth = None
        if self.yarn_endpoint_security_enabled:
            from requests_kerberos import HTTPKerberosAuth
            auth = HTTPKerberosAuth()

        self.resource_mgr = ResourceManager(service_endpoints=endpoints, auth=auth)

        self.rm_addr = self.resource_mgr.get_active_endpoint()

        # YARN applications tend to take longer than the default 5 second wait time.  Rather than
        # require a command-line option for those using YARN, we'll adjust based on a local env that
        # defaults to 15 seconds.  Note: we'll only adjust if the current wait time is shorter than
        # the desired value.
        if kernel_manager.shutdown_wait_time < yarn_shutdown_wait_time:
            kernel_manager.shutdown_wait_time = yarn_shutdown_wait_time
            self.log.debug("{class_name} shutdown wait time adjusted to {wait_time} seconds.".
                           format(class_name=type(self).__name__, wait_time=kernel_manager.shutdown_wait_time))

        # If yarn resource check is enabled and it isn't available immediately,
        # 20% of kernel_launch_timeout is used to wait
        # and retry at fixed interval before pronouncing as not feasible to launch.
        self.yarn_resource_check_wait_time = 0.20 * self.kernel_launch_timeout

    async def launch_process(self, kernel_cmd, **kwargs):
        """Launches the specified process within a YARN cluster environment."""

        # checks to see if the queue resource is available
        # if not available, kernel startup is not attempted
        self.confirm_yarn_queue_availability(**kwargs)

        await super(YarnClusterProcessProxy, self).launch_process(kernel_cmd, **kwargs)

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.debug("Yarn cluster kernel launched using YARN RM address: {}, pid: {}, Kernel ID: {}, cmd: '{}'"
                       .format(self.rm_addr, self.local_proc.pid, self.kernel_id, kernel_cmd))
        await self.confirm_remote_startup()
        return self

    def confirm_yarn_queue_availability(self, **kwargs):
        """
        Submitting jobs to yarn queue and then checking till the jobs are in running state
        will lead to orphan jobs being created in some scenarios.

        We take kernel_launch_timeout time and divide this into two parts.
        If the queue is unavailable we take max 20% of the time to poll the queue periodically
        and if the queue becomes available the rest of timeout is met in 80% of the remaining
        time.

        This algorithm is subject to change. Please read the below cases to understand
        when and how checks are applied.

        Confirms if the yarn queue has capacity to handle the resource requests that
        will be sent to it.

        First check ensures the driver and executor memory request falls within
        the container size of yarn configuration. This check requires executor and
        driver memory to be available in the env.

        Second,Current version of check, takes into consideration node label partitioning
        on given queues. Provided the queue name and node label this checks if
        the given partition has capacity available for kernel startup.

        All Checks are optional. If we have KERNEL_EXECUTOR_MEMORY and KERNEL_DRIVER_MEMORY
        specified, first check is performed.

        If we have KERNEL_QUEUE and KERNEL_NODE_LABEL specified, second check is performed.

        Proper error messages are sent back for user experience
        :param kwargs:
        :return:
        """
        env_dict = kwargs.get('env', {})

        executor_memory = int(env_dict.get('KERNEL_EXECUTOR_MEMORY', 0))
        driver_memory = int(env_dict.get('KERNEL_DRIVER_MEMORY', 0))

        if executor_memory * driver_memory > 0:
            container_memory = self.resource_mgr.cluster_node_container_memory()
            if max(executor_memory, driver_memory) > container_memory:
                self.log_and_raise(http_status_code=500,
                                   reason="Container Memory not sufficient for a executor/driver allocation")

        candidate_queue_name = (env_dict.get('KERNEL_QUEUE', None))
        node_label = env_dict.get('KERNEL_NODE_LABEL', None)
        partition_availability_threshold = float(env_dict.get('YARN_PARTITION_THRESHOLD', 95.0))

        if candidate_queue_name is None or node_label is None:
            return

        # else the resources may or may not be available now. it may be possible that if we wait then the resources
        # become available. start  a timeout process

        self.start_time = RemoteProcessProxy.get_current_time()
        self.candidate_queue = self.resource_mgr.cluster_scheduler_queue(candidate_queue_name)

        if self.candidate_queue is None:
            self.log.warning("Queue: {} not found in cluster."
                             "Availability check will not be performed".format(candidate_queue_name))
            return

        self.candidate_partition = self.resource_mgr.cluster_queue_partition(self.candidate_queue, node_label)

        if self.candidate_partition is None:
            self.log.debug("Partition: {} not found in {} queue."
                           "Availability check will not be performed".format(node_label, candidate_queue_name))
            return

        self.log.debug("Checking endpoint: {} if partition: {} "
                       "has used capacity <= {}%".format(self.yarn_endpoint,
                                                         self.candidate_partition, partition_availability_threshold))

        yarn_available = self.resource_mgr.cluster_scheduler_queue_availability(self.candidate_partition,
                                                                                partition_availability_threshold)
        if not yarn_available:
            self.log.debug(
                "Retrying for {} ms since resources are not available".format(self.yarn_resource_check_wait_time))
            while not yarn_available:
                self.handle_yarn_queue_timeout()
                yarn_available = self.resource_mgr.cluster_scheduler_queue_availability(
                    self.candidate_partition, partition_availability_threshold)

        # subtracting the total amount of time spent for polling for queue availability
        self.kernel_launch_timeout -= RemoteProcessProxy.get_time_diff(self.start_time,
                                                                       RemoteProcessProxy.get_current_time())

    def handle_yarn_queue_timeout(self):

        time.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.yarn_resource_check_wait_time:
            error_http_code = 500
            reason = "Yarn Compute Resource is unavailable after {} seconds".format(self.yarn_resource_check_wait_time)
            self.log_and_raise(http_status_code=error_http_code, reason=reason)

    def poll(self):
        """Submitting a new kernel/app to YARN will take a while to be ACCEPTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in ACCEPTED or SUBMITTED state.

        :return: None if the application's ID is available and state is ACCEPTED/SUBMITTED/RUNNING. Otherwise False.
        """
        result = False

        if self._get_application_id():
            state = self._query_app_state_by_id(self.application_id)
            if state in YarnClusterProcessProxy.initial_states:
                result = None

        # The following produces too much output (every 3 seconds by default), so commented-out at this time.
        # self.log.debug("YarnProcessProxy.poll, application ID: {}, kernel ID: {}, state: {}".
        #               format(self.application_id, self.kernel_id, state))
        return result

    def send_signal(self, signum):
        """Currently only support 0 as poll and other as kill.

        :param signum
        :return:
        """
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            # Yarn api doesn't support the equivalent to interrupts, so take our chances
            # via a remote signal.  Note that this condition cannot check against the
            # signum value because altternate interrupt signals might be in play.
            return super(YarnClusterProcessProxy, self).send_signal(signum)

    def kill(self):
        """Kill a kernel.
        :return: None if the application existed and is not in RUNNING state, False otherwise.
        """
        state = None
        result = False
        if self._get_application_id():
            self._kill_app_by_id(self.application_id)
            # Check that state has moved to a final state (most likely KILLED)
            i = 1
            state = self._query_app_state_by_id(self.application_id)
            while state not in YarnClusterProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = self._query_app_state_by_id(self.application_id)
                i = i + 1

            if state in YarnClusterProcessProxy.final_states:
                result = None

        if result is False:  # We couldn't terminate via Yarn, try remote signal
            result = super(YarnClusterProcessProxy, self).kill()

        self.log.debug("YarnClusterProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}, result: {}"
                       .format(self.application_id, self.kernel_id, state, result))
        return result

    def cleanup(self):
        """"""
        # we might have a defunct process (if using waitAppCompletion = false) - so poll, kill, wait when we have
        # a local_proc.
        if self.local_proc:
            self.log.debug("YarnClusterProcessProxy.cleanup: Clearing possible defunct process, pid={}...".
                           format(self.local_proc.pid))
            if super(YarnClusterProcessProxy, self).poll():
                super(YarnClusterProcessProxy, self).kill()
            super(YarnClusterProcessProxy, self).wait()
            self.local_proc = None

        # reset application id to force new query - handles kernel restarts/interrupts
        self.application_id = None

        # for cleanup, we should call the superclass last
        super(YarnClusterProcessProxy, self).cleanup()

    async def confirm_remote_startup(self):
        """ Confirms the yarn application is in a started state before returning.  Should post-RUNNING states be
            unexpectedly encountered (FINISHED, KILLED, FAILED) then we must throw,
            otherwise the rest of the gateway will believe its talking to a valid kernel.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            await self.handle_timeout()

            if self._get_application_id(True):
                # Once we have an application ID, start monitoring state, obtain assigned host and get connection info
                app_state = self._get_application_state()

                if app_state in YarnClusterProcessProxy.final_states:
                    error_message = "KernelID: '{}', ApplicationID: '{}' unexpectedly found in state '{}'" \
                                    " during kernel startup!".format(self.kernel_id, self.application_id, app_state)
                    self.log_and_raise(http_status_code=500, reason=error_message)

                self.log.debug("{}: State: '{}', Host: '{}', KernelID: '{}', ApplicationID: '{}'".
                               format(i, app_state, self.assigned_host, self.kernel_id, self.application_id))

                if self.assigned_host != '':
                    ready_to_connect = await self.receive_connection_info()
            else:
                self.detect_launch_failure()

    async def handle_timeout(self):
        """Checks to see if the kernel launch timeout has been exceeded while awaiting connection info."""
        await asyncio.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            reason = "Application ID is None. Failed to submit a new application to YARN within {} seconds.  " \
                     "Check Enterprise Gateway log for more information.". \
                format(self.kernel_launch_timeout)
            error_http_code = 500
            if self._get_application_id(True):
                if self._query_app_state_by_id(self.application_id) != "RUNNING":
                    reason = "YARN resources unavailable after {} seconds for app {}, launch timeout: {}!  " \
                             "Check YARN configuration.".format(time_interval, self.application_id,
                                                                self.kernel_launch_timeout)
                    error_http_code = 503
                else:
                    reason = "App {} is RUNNING, but waited too long ({} secs) to get connection file.  " \
                             "Check YARN logs for more information.".format(self.application_id,
                                                                            self.kernel_launch_timeout)
            self.kill()
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log_and_raise(http_status_code=error_http_code, reason=timeout_message)

    def get_process_info(self):
        """Captures the base information necessary for kernel persistence relative to YARN clusters."""
        process_info = super(YarnClusterProcessProxy, self).get_process_info()
        process_info.update({'application_id': self.application_id})
        return process_info

    def load_process_info(self, process_info):
        """Loads the base information necessary for kernel persistence relative to YARN clusters."""
        super(YarnClusterProcessProxy, self).load_process_info(process_info)
        self.application_id = process_info['application_id']

    def _get_application_state(self):
        # Gets the current application state using the application_id already obtained.  Once the assigned host
        # has been identified, 'amHostHttpAddress' is nolonger accessed.
        app_state = self.last_known_state
        app = self._query_app_by_id(self.application_id)
        if app:
            if app.get('state'):
                app_state = app.get('state')
                self.last_known_state = app_state

            if self.assigned_host == '' and app.get('amHostHttpAddress'):
                self.assigned_host = app.get('amHostHttpAddress').split(':')[0]
                # Set the kernel manager ip to the actual host where the application landed.
                self.assigned_ip = socket.gethostbyname(self.assigned_host)

        return app_state

    def _get_application_id(self, ignore_final_states=False):
        # Return the kernel's YARN application ID if available, otherwise None.  If we're obtaining application_id
        # from scratch, do not consider kernels in final states.
        if not self.application_id:
            app = self._query_app_by_name(self.kernel_id)
            state_condition = True
            if type(app) is dict:
                state = app.get('state')
                self.last_known_state = state

                if ignore_final_states:
                    state_condition = state not in YarnClusterProcessProxy.final_states

                if len(app.get('id', '')) > 0 and state_condition:
                    self.application_id = app['id']
                    time_interval = RemoteProcessProxy.get_time_diff(self.start_time,
                                                                     RemoteProcessProxy.get_current_time())
                    self.log.info("ApplicationID: '{}' assigned for KernelID: '{}', "
                                  "state: {}, {} seconds after starting."
                                  .format(app['id'], self.kernel_id, state, time_interval))
            if not self.application_id:
                self.log.debug("ApplicationID not yet assigned for KernelID: '{}' - retrying...".format(self.kernel_id))
        return self.application_id

    def _query_app_by_name(self, kernel_id):
        """Retrieve application by using kernel_id as the unique app name.
        With the started_time_begin as a parameter to filter applications started earlier than the target one from YARN.
        When submit a new app, it may take a while for YARN to accept and run and generate the application ID.
        Note: if a kernel restarts with the same kernel id as app name, multiple applications will be returned.
        For now, the app/kernel with the top most application ID will be returned as the target app, assuming the app
        ID will be incremented automatically on the YARN side.

        :param kernel_id: as the unique app name for query
        :return: The JSON object of an application.
        """
        top_most_app_id = ''
        target_app = None
        try:
            response = self.resource_mgr.cluster_applications(started_time_begin=str(self.start_time))
        except socket.error as sock_err:
            if sock_err.errno == errno.ECONNREFUSED:
                self.log.warning("YARN RM address: '{}' refused the connection.  Is the resource manager running?".
                                 format(self.rm_addr))
            else:
                self.log.warning("Query for kernel ID '{}' failed with exception: {} - '{}'.  Continuing...".
                                 format(kernel_id, type(sock_err), sock_err))
        except Exception as e:
            self.log.warning("Query for kernel ID '{}' failed with exception: {} - '{}'.  Continuing...".
                             format(kernel_id, type(e), e))
        else:
            data = response.data
            if type(data) is dict and type(data.get("apps")) is dict and 'app' in data.get("apps"):
                for app in data['apps']['app']:
                    if app.get('name', '').find(kernel_id) >= 0 and app.get('id') > top_most_app_id:
                        target_app = app
                        top_most_app_id = app.get('id')
        return target_app

    def _query_app_by_id(self, app_id):
        """Retrieve an application by application ID.

        :param app_id
        :return: The JSON object of an application.
        """
        app = None
        try:
            response = self.resource_mgr.cluster_application(application_id=app_id)
        except Exception as e:
            self.log.warning("Query for application ID '{}' failed with exception: '{}'.  Continuing...".
                             format(app_id, e))
        else:
            data = response.data
            if type(data) is dict and 'app' in data:
                app = data['app']

        return app

    def _query_app_state_by_id(self, app_id):
        """Return the state of an application. If a failure occurs, the last known state is returned.

        :param app_id:
        :return: application state (str)
        """
        state = self.last_known_state
        try:
            response = self.resource_mgr.cluster_application_state(application_id=app_id)
        except Exception as e:
            self.log.warning("Query for application '{}' state failed with exception: '{}'.  "
                             "Continuing with last known state = '{}'...".
                             format(app_id, e, state))
        else:
            state = response.data['state']
            self.last_known_state = state

        return state

    def _kill_app_by_id(self, app_id):
        """Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.

        :param app_id
        :return: The JSON response of killing the application.
        """

        response = None
        try:
            response = self.resource_mgr.cluster_application_kill(application_id=app_id)
        except Exception as e:
            self.log.warning("Termination of application '{}' failed with exception: '{}'.  Continuing...".
                             format(app_id, e))

        return response
