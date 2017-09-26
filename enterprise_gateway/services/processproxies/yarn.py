# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import signal
import json
import time
import tornado
import logging
import subprocess
from socket import *
from tornado import web
from jupyter_client import launch_kernel, localinterfaces
from .processproxy import RemoteProcessProxy
from yarn_api_client.resource_manager import ResourceManager
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

# Default logging level of yarn-api produces too much noise - raise to warning only.
logging.getLogger('yarn_api_client.resource_manager').setLevel(os.getenv('EG_YARN_LOG_LEVEL', logging.WARNING))

local_ip = localinterfaces.public_ips()[0]
poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
max_poll_attempts = int(os.getenv('EG_MAX_POLL_ATTEMPTS', '10'))


class YarnClusterProcessProxy(RemoteProcessProxy):
    initial_states = {'NEW', 'SUBMITTED', 'ACCEPTED', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED'}  # Don't include FAILED state

    def __init__(self, kernel_manager):
        super(YarnClusterProcessProxy, self).__init__(kernel_manager)
        self.application_id = None
        self.yarn_endpoint = kernel_manager.parent.parent.yarn_endpoint # from command line or env
        yarn_master = urlparse(self.yarn_endpoint).hostname
        self.resource_mgr = ResourceManager(address=yarn_master)

    def launch_process(self, kernel_cmd, **kw):
        """ Launches the Yarn process.  Prior to invocation, connection files will be distributed to each applicable
            Yarn node so that its in place when the kernel is started.  This step is skipped if pull or socket modes 
            are configured, which results in the kernel process determining ports and generating encoding key.
            Once started, the method will poll the Yarn application (after discovering the application ID via the
            kernel ID) until host is known.  Note that this polling may timeout and result in a 503 Http error (Service 
            unavailable).
            Once the host is determined the connection file is retrieved. If pull mode is configured, the remote file is 
            copied locally and member variables are loaded based on its contents.  If socket mode is configured, the
            kernel launcher sends the connection information - which is then written out upon its reception.  If push
            mode is configured, the kernel manager's IP is updated to the selected node.
        """
        super(YarnClusterProcessProxy, self).launch_process(kernel_cmd, **kw)

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.debug("Yarn cluster kernel launched using YARN endpoint: {}, pid: {}, Kernel ID: {}, cmd: '{}'"
                       .format(self.yarn_endpoint, self.local_proc.pid, self.kernel_id, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

        return self

    def poll(self):
        """Submitting a new kernel/app to YARN will take a while to be ACCEPTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in ACCEPTED or SUBMITTED state.

        :return: None if the application's ID is available and state is ACCEPTED/SUBMITTED/RUNNING. Otherwise False. 
        """
        result = False

        if self.get_application_id():
            state = self.query_app_state_by_id(self.application_id)
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
        self.log.debug("YarnClusterProcessProxy.send_signal {}".format(signum))
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
        if self.get_application_id():
            resp = self.kill_app_by_id(self.application_id)
            self.log.debug(
                "YarnClusterProcessProxy.kill: kill_app_by_id({}) response: {}, confirming app state is not RUNNING"
                    .format(self.application_id, resp))

            i, state = 1, self.query_app_state_by_id(self.application_id)
            while state not in YarnClusterProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = self.query_app_state_by_id(self.application_id)
                i = i + 1

            if state in YarnClusterProcessProxy.final_states:
                result = None

        super(YarnClusterProcessProxy, self).kill()

        self.log.debug("YarnClusterProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}"
                       .format(self.application_id, self.kernel_id, state))
        return result

    def cleanup(self):
        super(YarnClusterProcessProxy, self).cleanup()

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
        self.assigned_ip = None

    def confirm_remote_startup(self, kernel_cmd, **kw):
        """ Confirms the yarn application is in a started state before returning.  Should post-RUNNING states be
            unexpectedly encountered (FINISHED, KILLED) then we must throw, otherwise the rest of the JKG will
            believe its talking to a valid kernel.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            self.handle_timeout()

            if self.get_application_id(True):
                # Once we have an application ID, start monitoring state, obtain assigned host and get connection info
                app_state = self.get_application_state()

                if app_state in YarnClusterProcessProxy.final_states:
                    raise tornado.web.HTTPError(500, "KernelID: '{}', ApplicationID: '{}' unexpectedly found in"
                                                     "state '{}' during kernel startup!".format(self.kernel_id,
                                                                                                self.application_id,
                                                                                                app_state))

                self.log.debug("{}: State: '{}', Host: '{}', KernelID: '{}', ApplicationID: '{}'".
                               format(i, app_state, self.assigned_host, self.kernel_id, self.application_id))

                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()

    def get_application_state(self):
        # Gets the current application state using the application_id already obtained.  Once the assigned host
        # has been identified, it is nolonger accessed.
        app_state = None
        app = self.query_app_by_id(self.application_id)

        if app:
            if app.get('state'):
                app_state = app.get('state')
            if self.assigned_host == '' and app.get('amHostHttpAddress'):
                self.assigned_host = app.get('amHostHttpAddress').split(':')[0]
                # Set the kernel manager ip to the actual host where the application landed.
                self.assigned_ip = gethostbyname(self.assigned_host)
        return app_state

    def handle_timeout(self):
        time.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            reason = "Application ID is None. Failed to submit a new application to YARN within {} seconds.". \
                format(self.kernel_launch_timeout)
            error_http_code = 500
            if self.get_application_id(True):
                if self.query_app_state_by_id(self.application_id) != "RUNNING":
                    reason = "YARN resources unavailable after {} seconds for app {}, launch timeout: {}!". \
                        format(time_interval, self.application_id, self.kernel_launch_timeout)
                    error_http_code = 503
                else:
                    reason = "App {} is RUNNING, but waited too long ({} secs) to get connection file". \
                        format(self.application_id, self.kernel_launch_timeout)
            self.kill()
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log.error(timeout_message)
            raise tornado.web.HTTPError(error_http_code, timeout_message)

    def get_application_id(self, ignore_final_states=False):
        # Return the kernel's YARN application ID if available, otherwise None.  If we're obtaining application_id
        # from scratch, do not consider kernels in final states.
        if not self.application_id:
            app = self.query_app_by_name(self.kernel_id)
            state_condition = True
            if type(app) is dict and ignore_final_states:
                state_condition = app.get('state') not in YarnClusterProcessProxy.final_states

            if type(app) is dict and len(app.get('id', '')) > 0 and state_condition:
                self.application_id = app['id']
                time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())
                self.log.info("ApplicationID: '{}' assigned for KernelID: '{}', state: {}, {} seconds after starting."
                              .format(app['id'], self.kernel_id, app.get('state'), time_interval))
            else:
                self.log.debug("ApplicationID not yet assigned for KernelID: '{}' - retrying...".format(self.kernel_id))
        return self.application_id

    def get_process_info(self):
        process_info = super(YarnClusterProcessProxy, self).get_process_info()
        process_info.update({'application_id': self.application_id})
        return process_info

    def load_process_info(self, process_info):
        super(YarnClusterProcessProxy, self).load_process_info(process_info)
        self.application_id = process_info['application_id']

    def query_app_by_name(self, kernel_id):
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
        data = self.resource_mgr.cluster_applications(started_time_begin=str(self.start_time)).data
        if type(data) is dict and type(data.get("apps")) is dict and 'app' in data.get("apps"):
            for app in data['apps']['app']:
                if app.get('name', '').find(kernel_id) >= 0 and app.get('id') > top_most_app_id:
                    target_app = app
                    top_most_app_id = app.get('id')
        return target_app

    def query_app_by_id(self, app_id):
        """Retrieve an application by application ID.

        :param app_id
        :return: The JSON object of an application.
        """
        data = self.resource_mgr.cluster_application(application_id=app_id).data
        if type(data) is dict and 'app' in data:
            return data['app']
        return None

    def query_app_state_by_id(self, app_id):
        """Return the state of an application.

        :param app_id: 
        :return: 
        """
        url = '%s/apps/%s/state' % (self.yarn_endpoint, app_id)
        cmd = ['curl', '-X', 'GET', url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        output, stderr = process.communicate()
        return json.loads(output).get('state') if output else None

    def kill_app_by_id(self, app_id):
        """Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.
        TODO: extend the yarn_api_client to support cluster_application_kill with PUT, e.g.:
            YarnProcessProxy.resource_mgr.cluster_application_kill(application_id=app_id)

        :param app_id 
        :return: The JSON response of killing the application.
        """
        header = "Content-Type: application/json"
        data = '{"state": "KILLED"}'
        url = '%s/apps/%s/state' % (self.yarn_endpoint, app_id)
        cmd = ['curl', '-X', 'PUT', '-H', header, '-d', data, url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        output, stderr = process.communicate()
        return json.loads(output) if output else None
