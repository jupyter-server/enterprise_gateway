# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import signal
import json
import time
import subprocess
import socket
import re
from jupyter_client import launch_kernel, localinterfaces
from .processproxy import RemoteProcessProxy

pjoin = os.path.join

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

local_ip = localinterfaces.public_ips()[0]
poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
max_poll_attempts = int(os.getenv('EG_MAX_POLL_ATTEMPTS', '10'))


class ConductorClusterProcessProxy(RemoteProcessProxy):
    initial_states = {'SUBMITTED', 'WAITING', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED', 'RECLAIMED'}  # Don't include FAILED state

    def __init__(self, kernel_manager, proxy_config):
        super(ConductorClusterProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.application_id = None
        self.driver_id = None
        self.conductor_endpoint = proxy_config.get('conductor_endpoint', kernel_manager.parent.parent.conductor_endpoint)

    def launch_process(self, kernel_cmd, **kw):
        """ Launches the kernel process.
        """
        super(ConductorClusterProcessProxy, self).launch_process(kernel_cmd, **kw)
        # Get cred from process env
        env_dict = dict(os.environ.copy())
        if env_dict and 'EGO_SERVICE_CREDENTIAL' in env_dict:
            self.rest_credential = env_dict['EGO_SERVICE_CREDENTIAL']
        else:
            error_message = "ConductorClusterProcessProxy failed to obtain the Conductor credential."
            self.log_and_raise(http_status_code=500, reason=error_message)

        # dynamically update Spark submit parameters
        self.update_launch_info(kernel_cmd, **kw)
        # Enable stderr PIPE for the run command
        kw.update({'stderr': subprocess.PIPE})
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip
        self.env = kw.get('env')
        self.log.debug("Conductor cluster kernel launched using Conductor endpoint: {}, pid: {}, Kernel ID: {}, cmd: '{}'"
                       .format(self.conductor_endpoint, self.local_proc.pid, self.kernel_id, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

        return self

    def update_launch_info(self, kernel_cmd, **kw):
        """ Dynamically assemble the spark-submit configuration passed from NB2KG
        """
        if any(arg.endswith('.sh') for arg in kernel_cmd):
            self.log.debug("kernel_cmd contains execution script")
        else: 
            kernel_dir = self.kernel_manager.kernel_spec_manager._find_spec_directory(self.kernel_manager.kernel_name)
            cmd = pjoin(kernel_dir, 'bin/run.sh')
            kernel_cmd.insert(0, cmd)

        env_dict = kw.get('env')
        # add SPARK_HOME, PYSPARK_PYTHON, update SPARK_OPT to contain SPARK_MASTER and EGO_SERVICE_CREDENTIAL
        env_dict['SPARK_HOME'] = env_dict['KERNEL_SPARK_HOME']
        env_dict['PYSPARK_PYTHON'] = env_dict['KERNEL_PYSPARK_PYTHON']
        # add KERNEL_SPARK_OPTS to append user configured Spark configuration
        user_defined_spark_opts = ''
        if 'KERNEL_SPARK_OPTS' in env_dict:
            user_defined_spark_opts = env_dict['KERNEL_SPARK_OPTS']

        if "--master" not in env_dict['SPARK_OPTS']:
            env_dict['SPARK_OPTS'] = '--master %s --conf spark.ego.credential=%s --conf spark.pyspark.python=%s %s %s' % \
            (env_dict['KERNEL_NOTEBOOK_MASTER_REST'], self.rest_credential, env_dict['PYSPARK_PYTHON'], env_dict['SPARK_OPTS'], user_defined_spark_opts)

    def poll(self):
        """Submitting a new kernel/app will take a while to be SUBMITTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in SUBMITTED/WAITING/RUNNING state.

        :return: None if the application's ID is available and state is SUBMITTED/WAITING/RUNNING. Otherwise False. 
        """
        result = False

        if self.get_application_id():
            state = self.query_app_state_by_id(self.application_id)
            if state in ConductorClusterProcessProxy.initial_states:
                result = None
        return result

    def send_signal(self, signum):
        """Currently only support 0 as poll and other as kill.

        :param signum
        :return: 
        """
        self.log.debug("ConductorClusterProcessProxy.send_signal {}".format(signum))
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGKILL:
            return self.kill()
        else:
            return super(ConductorClusterProcessProxy, self).send_signal(signum)

    def kill(self):
        """Kill a kernel.
        :return: None if the application existed and is not in RUNNING state, False otherwise. 
        """
        state = None
        result = False
        if self.driver_id:
            resp = self.kill_app_by_driver_id(self.driver_id)
            self.log.debug(
                "ConductorClusterProcessProxy.kill: kill_app_by_driver_id({}) response: {}, confirming app state is not RUNNING"
                    .format(self.driver_id, resp))

            i = 1
            state = self.query_app_state_by_id(self.application_id)
            while state not in ConductorClusterProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = self.query_app_state_by_id(self.application_id)
                i = i + 1

            if state in ConductorClusterProcessProxy.final_states:
                result = None

        super(ConductorClusterProcessProxy, self).kill()

        self.log.debug("ConductorClusterProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}"
                       .format(self.application_id, self.kernel_id, state))
        return result

    def cleanup(self):
        # we might have a defunct process (if using waitAppCompletion = false) - so poll, kill, wait when we have
        # a local_proc.
        if self.local_proc:
            self.log.debug("ConductorClusterProcessProxy.cleanup: Clearing possible defunct process, pid={}...".
                           format(self.local_proc.pid))
            if super(ConductorClusterProcessProxy, self).poll():
                super(ConductorClusterProcessProxy, self).kill()
            super(ConductorClusterProcessProxy, self).wait()
            self.local_proc = None

        # reset application id to force new query - handles kernel restarts/interrupts
        self.application_id = None

        # for cleanup, we should call the superclass last
        super(ConductorClusterProcessProxy, self).cleanup()

    def parse_driver_submission_id(self, submission_response):
        """ Parse driver id from stderr gotten back from launch_kernel
        :param submission_response
        """
        if submission_response:
            self.log.debug("Submission Response: {}\n".format(submission_response))
            matched_lines = [line for line in submission_response.split('\n') if "submissionId" in line] 
            if matched_lines and len(matched_lines) > 0:
                driver_info = matched_lines[0]
                self.log.debug("Driver Info: {}".format(driver_info))
                driver_id = driver_info.split(":")[1]
                driver_id = re.findall(r'"([^"]*)"', driver_id)
                if driver_id and len(driver_id) > 0:
                    self.driver_id = driver_id[0]
                    self.log.debug("Driver ID: {}".format(driver_id[0]))

    def confirm_remote_startup(self, kernel_cmd, **kw):
        """ Confirms the application is in a started state before returning.  Should post-RUNNING states be
            unexpectedly encountered ('FINISHED', 'KILLED', 'RECLAIMED') then we must throw, otherwise the rest of the JKG will
            believe its talking to a valid kernel.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            if self.local_proc.stderr:
                # Read stderr after the launch_kernel, and parse the driver id from the REST response
                output = self.local_proc.stderr.read().decode("utf-8")   
                self.parse_driver_submission_id(output)
            i += 1
            self.handle_timeout()

            if self.get_application_id(True):
                # Once we have an application ID, start monitoring state, obtain assigned host and get connection info
                app_state = self.get_application_state()

                if app_state in ConductorClusterProcessProxy.final_states:
                    error_message = "KernelID: '{}', ApplicationID: '{}' unexpectedly found in " \
                                                     "state '{}' during kernel startup!".\
                                    format(self.kernel_id, self.application_id, app_state)
                    self.log_and_raise(http_status_code=500, reason=error_message)

                self.log.debug("{}: State: '{}', Host: '{}', KernelID: '{}', ApplicationID: '{}'".
                               format(i, app_state, self.assigned_host, self.kernel_id, self.application_id))

                if self.assigned_host != '':
                    ready_to_connect = self.receive_connection_info()

    def get_application_state(self):
        # Gets the current application state using the application_id already obtained.  Once the assigned host
        # has been identified, it is no longer accessed.
        app_state = None
        apps = self.query_app_by_driver_id(self.driver_id)

        if apps:
            for app in apps:
                if 'state' in app:
                    app_state = app['state']
                if self.assigned_host == '' and app['driver']:
                    self.assigned_host = app['driver']['host']
                    # Set the driver host to the actual host where the application landed.
                    self.assigned_ip = socket.gethostbyname(self.assigned_host)
        return app_state

    def handle_timeout(self):
        time.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            reason = "Application failed to start within {} seconds.". \
                format(self.kernel_launch_timeout)
            error_http_code = 500
            if self.get_application_id(True):
                if self.query_app_state_by_id(self.application_id) != "WAITING":
                    reason = "Kernel unavailable after {} seconds for app {}, launch timeout: {}!". \
                        format(time_interval, self.application_id, self.kernel_launch_timeout)
                    error_http_code = 503
                else:
                    reason = "App {} is WAITING, but waited too long ({} secs) to get connection file". \
                        format(self.application_id, self.kernel_launch_timeout)
            self.kill()
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log_and_raise(http_status_code=error_http_code, reason=timeout_message)

    def get_application_id(self, ignore_final_states=False):
        # Return the kernel's application ID if available, otherwise None.  If we're obtaining application_id
        # from scratch, do not consider kernels in final states.
        if not self.application_id:
            apps = self.query_app_by_driver_id(self.driver_id)
            state_condition = True
            if apps:
                for app in apps:
                    if 'state' in app and ignore_final_states:
                        state_condition = app['state'] not in ConductorClusterProcessProxy.final_states
                    if 'applicationid' in app and len(app['applicationid']) > 0 and state_condition:
                        self.application_id = app['applicationid']
                        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())
                        self.log.info("ApplicationID: '{}' assigned for KernelID: '{}', state: {}, {} seconds after starting."
                                      .format(app['applicationid'], self.kernel_id, app['state'], time_interval))
                    else:
                        self.log.debug("ApplicationID not yet assigned for KernelID: '{}' - retrying...".format(self.kernel_id))
            else:
                self.log.debug("ApplicationID not yet assigned for KernelID: '{}' - retrying...".format(self.kernel_id))
        return self.application_id

    def get_process_info(self):
        process_info = super(ConductorClusterProcessProxy, self).get_process_info()
        process_info.update({'application_id': self.application_id})
        return process_info

    def load_process_info(self, process_info):
        super(ConductorClusterProcessProxy, self).load_process_info(process_info)
        self.application_id = process_info['application_id']

    def query_app_by_driver_id(self, driver_id):
        """Retrieve application by using driver ID.

        :param driver_id: as the unique driver id for query
        :return: The JSON object of an application. None if driver_id is not found.
        """
        response = None
        if not driver_id:
            return response
        # Assemble REST call
        env = self.env
        header = 'Accept: application/json'
        authorization = 'Authorization: PlatformToken token=%s' % (self.rest_credential)
        cookie_jar = pjoin(env['KERNEL_NOTEBOOK_DATA_DIR'], env['KERNEL_NOTEBOOK_COOKIE_JAR'])
        sslconf = env['KERNEL_CURL_SECURITY_OPT'].split()
        url = '%s/v1/applications?driverid=%s' % (self.conductor_endpoint, driver_id)
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        
        # Perform REST call
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
            if not response or not response['applist']:
                response = None
            else:
                response = response['applist']
        except Exception as e:
            self.log.warning("Getting application with cmd '{}' failed with exception: '{}'.  Continuing...".
                           format(cmd, e))
        return response
    
    def query_app_by_id(self, app_id):
        """Retrieve an application by application ID.

        :param app_id
        :return: The JSON object of an application. None if app_id is not found.
        """
        response = None
        # Assemble REST call
        env = self.env
        header = 'Accept: application/json'
        authorization = 'Authorization: PlatformToken token=%s' % (self.rest_credential)
        cookie_jar = pjoin(env['KERNEL_NOTEBOOK_DATA_DIR'], env['KERNEL_NOTEBOOK_COOKIE_JAR'])
        sslconf = env['KERNEL_CURL_SECURITY_OPT'].split()
        url = '%s/v1/applications?applicationid=%s' % (self.conductor_endpoint, app_id)
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        # Perform REST call
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
            if response is None or not response['applist']:
                response = None
            else:
                response = response['applist']
        except Exception as e:
            self.log.warning("Getting application with cmd '{}' failed with exception: '{}'.  Continuing...".
                           format(cmd, e))
        return response
    
    def query_app_state_by_id(self, app_id):
        """Return the state of an application.

        :param app_id: 
        :return: 
        """
        response = None
        apps = self.query_app_by_driver_id(self.driver_id)
        if apps: 
            for app in apps:
                if 'state' in app:
                    response = app['state']
        return response

    def get_driver_by_app_id(self, app_id):
        """Get driver info from application ID.

        :param app_id
        :return: The JSON response driver information of the corresponding application. None if app_id is not found.
        """
        response = None
        apps = self.query_app_by_id(app_id)
        if apps:
            for app in apps:
                if app and app['driver']:
                    self.log.debug("Obtain Driver ID: {}".format(app['driver']['id']))
                    response = app['driver']
        else:
            self.log.warning("Application id does not exist")
        return response
    
    def kill_app_by_driver_id(self, driver_id):
        """Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.

        :param driver_id
        :return: The JSON response of killing the application. None if driver is not found.
        """
        self.log.debug("Kill driver: {}".format(driver_id))
        if driver_id is None:
            if self.application_id is None:
                return None 
            self.log.debug("Driver does not exist, retrieving DriverID with ApplicationID: {}".format(self.application_id))
            driver_info = self.get_driver_by_app_id(self.application_id)
            if driver_info:
                self.driver_id = driver_info['id']
            else:
                return None

        # Assemble REST call
        response = None
        env = self.env
        header = 'Accept: application/json'
        authorization = 'Authorization: PlatformToken token=%s' % (self.rest_credential)
        cookie_jar = pjoin(env['KERNEL_NOTEBOOK_DATA_DIR'], env['KERNEL_NOTEBOOK_COOKIE_JAR'])
        sslconf = env['KERNEL_CURL_SECURITY_OPT'].split()
        url = '%s/v1/submissions/kill/%s' % (self.conductor_endpoint, self.driver_id)
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'POST', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf

        # Perform REST call
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
        except Exception as e:
            self.log.warning("Termination of application with cmd '{}' failed with exception: '{}'.  Continuing...".
                           format(cmd, e))
        self.log.debug("Kill response: {}".format(response))
        return response