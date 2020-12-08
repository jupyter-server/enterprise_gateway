# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Code related to managing kernels running in Conductor clusters."""

import asyncio
import os
import json
import re
import signal
import socket
import subprocess
import time

from jupyter_client import localinterfaces

from .processproxy import RemoteProcessProxy

from notebook.utils import url_unescape

from random import randint

pjoin = os.path.join
local_ip = localinterfaces.public_ips()[0]
poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
max_poll_attempts = int(os.getenv('EG_MAX_POLL_ATTEMPTS', '10'))


class ConductorClusterProcessProxy(RemoteProcessProxy):
    """
    Kernel lifecycle management for Conductor clusters.
    """
    initial_states = {'SUBMITTED', 'WAITING', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED', 'RECLAIMED'}  # Don't include FAILED state

    def __init__(self, kernel_manager, proxy_config):
        super(ConductorClusterProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.application_id = None
        self.driver_id = None
        self.env = None
        self.rest_credential = None
        self.jwt_token = None
        self.conductor_endpoint = proxy_config.get('conductor_endpoint',
                                                   kernel_manager.conductor_endpoint)
        self.ascd_endpoint = self.conductor_endpoint

    async def launch_process(self, kernel_cmd, **kwargs):
        """
        Launches the specified process within a Conductor cluster environment.
        """
        await super(ConductorClusterProcessProxy, self).launch_process(kernel_cmd, **kwargs)

        self.env = kwargs.get('env')
        self.kernel_headers = kwargs.get('kernel_headers')

        # Get Conductor cred from process env
        env_dict = dict(os.environ.copy())
        if env_dict and 'EGO_SERVICE_CREDENTIAL' in env_dict:
            self.rest_credential = env_dict['EGO_SERVICE_CREDENTIAL']
        elif self.kernel_headers and 'Jwt-Auth-User-Payload' in self.kernel_headers:
            kwargs.get('env')['KERNEL_NOTEBOOK_COOKIE_JAR'] = 'kernelcookie' + str(randint(0, 1000))
            jsonKH = json.loads(self.kernel_headers['Jwt-Auth-User-Payload'])
            self.jwt_token = jsonKH['accessToken']
            await asyncio.get_event_loop().run_in_executor(None, self._performConductorJWTLogonAndRetrieval,
                                                           self.jwt_token, kwargs.get('env'))
        else:
            error_message = "ConductorClusterProcessProxy failed to obtain the Conductor credential."
            self.log_and_raise(http_status_code=500, reason=error_message)

        # dynamically update Spark submit parameters
        await asyncio.get_event_loop().run_in_executor(None, self._update_launch_info, kernel_cmd, kwargs.get('env'))
        # Enable stderr PIPE for the run command
        kwargs.update({'stderr': subprocess.PIPE})
        self.local_proc = self.launch_kernel(kernel_cmd, **kwargs)
        self.pid = self.local_proc.pid
        self.ip = local_ip

        self.log.debug("Conductor cluster kernel launched using Conductor endpoint: {}, pid: {}, Kernel ID: {}, "
                       "cmd: '{}'".format(self.conductor_endpoint, self.local_proc.pid, self.kernel_id, kernel_cmd))
        await self.confirm_remote_startup()
        return self

    def _update_launch_info(self, kernel_cmd, env_dict):
        """
        Dynamically assemble the spark-submit configuration passed from NB2KG.
        """
        if any(arg.endswith('.sh') for arg in kernel_cmd):
            self.log.debug("kernel_cmd contains execution script")
        else:
            kernel_dir = self.kernel_manager.kernel_spec_manager._find_spec_directory(self.kernel_manager.kernel_name)
            cmd = pjoin(kernel_dir, 'bin/run.sh')
            kernel_cmd.insert(0, cmd)

        # add SPARK_HOME, PYSPARK_PYTHON, update SPARK_OPT to contain SPARK_MASTER and EGO_SERVICE_CREDENTIAL
        env_dict['SPARK_HOME'] = env_dict['KERNEL_SPARK_HOME']
        env_dict['PYSPARK_PYTHON'] = env_dict['KERNEL_PYSPARK_PYTHON']
        # add KERNEL_SPARK_OPTS to append user configured Spark configuration
        user_defined_spark_opts = ''
        if 'KERNEL_SPARK_OPTS' in env_dict:
            user_defined_spark_opts = env_dict['KERNEL_SPARK_OPTS']

        # Get updated one_notebook_master_rest_url for KERNEL_NOTEBOOK_MASTER_REST and SPARK_OPTS.
        if self.jwt_token is None:
            self._update_notebook_master_rest_url(env_dict)

        if "--master" not in env_dict['SPARK_OPTS']:
            env_dict['SPARK_OPTS'] = '--master {master} --conf spark.ego.credential={rest_cred} ' \
                                     '--conf spark.pyspark.python={pyspark_python} {spark_opts} ' \
                                     '{user_defined_spark_opts}'.\
                format(master=env_dict['KERNEL_NOTEBOOK_MASTER_REST'], rest_cred="'" + self.rest_credential + "'",
                       pyspark_python=env_dict['PYSPARK_PYTHON'], spark_opts=env_dict['SPARK_OPTS'],
                       user_defined_spark_opts=user_defined_spark_opts)

    def _update_notebook_master_rest_url(self, env_dict):
        """
        Updates the notebook master rest url to update KERNEL_NOTEBOOK_MASTER_REST,
        conductor_endpoint, and SPARK_OPTS.
        """

        self.log.debug("Updating notebook master rest urls.")
        response = None
        # Assemble REST call
        header = 'Accept: application/json'
        authorization = 'Authorization: %s' % self.rest_credential
        if 'KERNEL_NOTEBOOK_DATA_DIR' not in env_dict or 'KERNEL_NOTEBOOK_COOKIE_JAR' not in env_dict \
                or 'KERNEL_CURL_SECURITY_OPT' not in env_dict:
            self.log.warning("Could not find KERNEL environment variables. Not updating notebook master rest url.")
            return
        if 'CONDUCTOR_REST_URL' not in env_dict or 'KERNEL_SIG_ID' not in env_dict \
                or 'KERNEL_NOTEBOOK_MASTER_REST' not in env_dict:
            self.log.warning("Could not find CONDUCTOR_REST_URL or KERNEL_SIG_ID or KERNEL_NOTEBOOK_MASTER_REST. "
                             "Not updating notebook master rest url.")
            return

        cookie_jar = pjoin(env_dict['KERNEL_NOTEBOOK_DATA_DIR'], env_dict['KERNEL_NOTEBOOK_COOKIE_JAR'])
        sslconf = env_dict['KERNEL_CURL_SECURITY_OPT'].split()
        ascd_rest_url = env_dict['CONDUCTOR_REST_URL']
        ig_id = env_dict['KERNEL_SIG_ID']
        url = '%sconductor/v1/instances?id=%s&fields=outputs' % (ascd_rest_url, ig_id)
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        # Perform REST call
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
            output, stderr = process.communicate()
            response = json.loads(output) if output else None
            if response is None or len(response) < 1 or not response[0] or not response[0]['outputs']:
                response = None
        except Exception as e:
            self.log.warning("Getting instance group with cmd '{}' failed with exception: '{}'.  Continuing...".
                             format(cmd, e))
            return

        outputs = response[0]['outputs']

        if 'one_notebook_master_rest_url' not in outputs or not outputs['one_notebook_master_rest_url'] \
            or 'value' not in outputs['one_notebook_master_rest_url'] \
                or not outputs['one_notebook_master_rest_url']['value']:
            self.log.warning("Could not get one_notebook_master_rest_url from instance group. "
                             "Not updating notebook master rest url.")
            return
        if 'one_notebook_master_web_submission_url' not in outputs \
            or not outputs['one_notebook_master_web_submission_url'] \
                or 'value' not in outputs['one_notebook_master_web_submission_url'] \
                or not outputs['one_notebook_master_web_submission_url']['value']:
            self.log.warning("Could not get one_notebook_master_web_submission_url from instance group. "
                             "Not updating notebook master rest url.")
            return

        updated_one_notebook_master_rest_url = outputs['one_notebook_master_rest_url']['value']
        updated_one_notebook_master_web_submission_url = outputs['one_notebook_master_web_submission_url']['value']

        if updated_one_notebook_master_rest_url and updated_one_notebook_master_web_submission_url:
            self.log.debug("Updating KERNEL_NOTEBOOK_MASTER_REST to '{}'.".format(updated_one_notebook_master_rest_url))
            os.environ['KERNEL_NOTEBOOK_MASTER_REST'] = updated_one_notebook_master_rest_url
            env_dict['KERNEL_NOTEBOOK_MASTER_REST'] = updated_one_notebook_master_rest_url
            self.conductor_endpoint = updated_one_notebook_master_web_submission_url

    def poll(self):
        """
        Submitting a new kernel/app will take a while to be SUBMITTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in SUBMITTED/WAITING/RUNNING state.
        :return: None if the application's ID is available and state is SUBMITTED/WAITING/RUNNING. Otherwise False.
        """
        result = False

        if self._get_application_id():
            state = self._query_app_state_by_driver_id(self.driver_id)
            if state in ConductorClusterProcessProxy.initial_states:
                result = None
        return result

    def send_signal(self, signum):
        """
        Currently only support 0 as poll and other as kill.
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
        """
        Kill a kernel.
        :return: None if the application existed and is not in RUNNING state, False otherwise.
        """
        state = None
        result = False
        if self.driver_id:
            resp = self._kill_app_by_driver_id(self.driver_id)
            self.log.debug("ConductorClusterProcessProxy.kill: kill_app_by_driver_id({}) response: {}, confirming "
                           "app state is not RUNNING".format(self.driver_id, resp))
            i = 1
            state = self._query_app_state_by_driver_id(self.driver_id)
            while state not in ConductorClusterProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = self._query_app_state_by_driver_id(self.driver_id)
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

    def _parse_driver_submission_id(self, submission_response):
        """
        Parse driver id from stderr gotten back from launch_kernel
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
            # Handle Checking for submission error to report
            err_lines = [line for line in submission_response.split('\n') if "Application submission failed" in line]
            if err_lines and len(err_lines) > 0:
                self.log_and_raise(http_status_code=500,
                                   reason=err_lines[0][err_lines[0].find("Application submission failed"):])

    async def confirm_remote_startup(self):
        """
        Confirms the application is in a started state before returning.  Should post-RUNNING states be
        unexpectedly encountered ('FINISHED', 'KILLED', 'RECLAIMED') then we must throw, otherwise the rest
        of the gateway will believe its talking to a valid kernel.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            if self.local_proc.stderr:
                # Read stderr after the launch_kernel, and parse the driver id from the REST response
                output = self.local_proc.stderr.read().decode("utf-8")
                self._parse_driver_submission_id(output)
            i += 1
            await self.handle_timeout()

            if self._get_application_id(True):
                # Once we have an application ID, start monitoring state, obtain assigned host and get connection info
                app_state = self._get_application_state()

                if app_state in ConductorClusterProcessProxy.final_states:
                    error_message = "KernelID: '{}', ApplicationID: '{}' unexpectedly found in state '{}' " \
                                    "during kernel startup!".\
                                    format(self.kernel_id, self.application_id, app_state)
                    self.log_and_raise(http_status_code=500, reason=error_message)

                self.log.debug("{}: State: '{}', Host: '{}', KernelID: '{}', ApplicationID: '{}'".
                               format(i, app_state, self.assigned_host, self.kernel_id, self.application_id))

                if self.assigned_host != '':
                    ready_to_connect = await self.receive_connection_info()
            else:
                self.detect_launch_failure()

    def _get_application_state(self):
        """
        Gets the current application state using the application_id already obtained.  Once the assigned host
        has been identified, it is no longer accessed.
        """
        app_state = None
        apps = self._query_app_by_driver_id(self.driver_id)

        if apps:
            for app in apps:
                if 'state' in app:
                    app_state = app['state']
                if self.assigned_host == '' and app['driver']:
                    self.assigned_host = app['driver']['host']
                    # Set the driver host to the actual host where the application landed.
                    self.assigned_ip = socket.gethostbyname(self.assigned_host)
        return app_state

    async def handle_timeout(self):
        """
        Checks to see if the kernel launch timeout has been exceeded while awaiting connection info.
        """
        await asyncio.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            reason = "Application failed to start within {} seconds.". \
                format(self.kernel_launch_timeout)
            error_http_code = 500
            if self._get_application_id(True):
                if self._query_app_state_by_driver_id(self.driver_id) != "WAITING":
                    reason = "Kernel unavailable after {} seconds for driver_id {}, app_id {}, launch timeout: {}!". \
                        format(time_interval, self.driver_id, self.application_id, self.kernel_launch_timeout)
                    error_http_code = 503
                else:
                    reason = "App {} is WAITING, but waited too long ({} secs) to get connection file". \
                        format(self.application_id, self.kernel_launch_timeout)
            await asyncio.get_event_loop().run_in_executor(None, self.kill)
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log_and_raise(http_status_code=error_http_code, reason=timeout_message)

    def _get_application_id(self, ignore_final_states=False):
        """
        Return the kernel's application ID if available, otherwise None.  If we're obtaining application_id
        from scratch, do not consider kernels in final states.
        """
        if not self.application_id:
            apps = self._query_app_by_driver_id(self.driver_id)
            state_condition = True
            if apps:
                for app in apps:
                    if 'state' in app and ignore_final_states:
                        state_condition = app['state'] not in ConductorClusterProcessProxy.final_states
                    if 'applicationid' in app and len(app['applicationid']) > 0 and state_condition:
                        self.application_id = app['applicationid']
                        time_interval = RemoteProcessProxy.get_time_diff(self.start_time,
                                                                         RemoteProcessProxy.get_current_time())
                        self.log.info("ApplicationID: '{}' assigned for KernelID: '{}', state: {}, "
                                      "{} seconds after starting.".format(app['applicationid'], self.kernel_id,
                                                                          app['state'], time_interval))
                    else:
                        self.log.debug("ApplicationID not yet assigned for KernelID: '{}' - retrying...".
                                       format(self.kernel_id))
            else:
                self.log.debug("ApplicationID not yet assigned for KernelID: '{}' - retrying...".
                               format(self.kernel_id))
        return self.application_id

    def get_process_info(self):
        """
        Captures the base information necessary for kernel persistence relative to Conductor clusters.
        """
        process_info = super(ConductorClusterProcessProxy, self).get_process_info()
        process_info.update({'application_id': self.application_id})
        process_info.update({'rest_credential': self.rest_credential})
        return process_info

    def load_process_info(self, process_info):
        """
        Captures the base information necessary for kernel persistence relative to Conductor clusters.
        """
        super(ConductorClusterProcessProxy, self).load_process_info(process_info)
        self.application_id = process_info['application_id']
        self.rest_credential = process_info['rest_credential']

    def _query_app_by_driver_id(self, driver_id):
        """
        Retrieve application by using driver ID.
        :param driver_id: as the unique driver id for query
        :return: The JSON object of an application. None if driver_id is not found.
        """
        response = None
        if not driver_id:
            return response
        # Assemble REST call
        env = self.env
        header = 'Accept: application/json'
        authorization = 'Authorization: %s' % self.rest_credential
        cookie_jar = pjoin(env['KERNEL_NOTEBOOK_DATA_DIR'], env['KERNEL_NOTEBOOK_COOKIE_JAR'])
        sslconf = env['KERNEL_CURL_SECURITY_OPT'].split()
        url = '%s/v1/applications?driverid=%s' % (self.conductor_endpoint, driver_id)
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
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

    def _query_app_by_id(self, app_id):
        """
        Retrieve an application by application ID.
        :param app_id
        :return: The JSON object of an application. None if app_id is not found.
        """
        response = None
        # Assemble REST call
        env = self.env
        header = 'Accept: application/json'
        authorization = 'Authorization: %s' % self.rest_credential
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

    def _query_app_state_by_driver_id(self, driver_id):
        """
        Return the state of an application.
        :param driver_id:
        :return:
        """
        response = None
        apps = self._query_app_by_driver_id(driver_id)
        if apps:
            for app in apps:
                if 'state' in app:
                    response = app['state']
        return response

    def _get_driver_by_app_id(self, app_id):
        """
        Get driver info from application ID.
        :param app_id
        :return: The JSON response driver information of the corresponding application. None if app_id is not found.
        """
        response = None
        apps = self._query_app_by_id(app_id)
        if apps:
            for app in apps:
                if app and app['driver']:
                    self.log.debug("Obtain Driver ID: {}".format(app['driver']['id']))
                    response = app['driver']
        else:
            self.log.warning("Application id does not exist")
        return response

    def _kill_app_by_driver_id(self, driver_id):
        """
        Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.
        :param driver_id
        :return: The JSON response of killing the application. None if driver is not found.
        """
        self.log.debug("Kill driver: {}".format(driver_id))
        if driver_id is None:
            if self.application_id is None:
                return None
            self.log.debug("Driver does not exist, retrieving DriverID with ApplicationID: {}".
                           format(self.application_id))
            driver_info = self._get_driver_by_app_id(self.application_id)
            if driver_info:
                self.driver_id = driver_info['id']
            else:
                return None

        # Assemble REST call
        response = None
        env = self.env
        header = 'Accept: application/json'
        authorization = 'Authorization: %s' % self.rest_credential
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

    def _performRestCall(self, cmd, url, HA_LIST):
        for HA in HA_LIST:
            portcolon = url.rfind(':')
            slash = url.find('://')
            url = url[0:slash + 3] + HA + url[portcolon:]
            cmd[-1] = url
            self.log.debug(cmd)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                       universal_newlines=True)
            output, stderr = process.communicate()
            if 'Could not resolve host' not in stderr and 'Failed connect to' not in stderr \
                    and 'Connection refused' not in stderr:
                return output, stderr
        self.log_and_raise(http_status_code=500, reason='Could not connect to ascd. Verify ascd is running.')
        return 'Error', 'Error'

    def _performConductorJWTLogonAndRetrieval(self, jwt_token, env_dict):
        """
        Authenticate to Conductor with a JWT Token and setup the kernel environment variables.
        :param jwt_token: JWT Token to authenticate with to Conductor
        :param env_dict: Environment Dictionary of this Kernel launch
        :return: None
        """
        response = None
        if not jwt_token:
            return response
        # Assemble JWT Auth logon REST call
        env = self.env

        if env['KERNEL_IG_UUID'] is None:
            reasonErr = 'Instance group specified is None. Check environment ' \
                        'specified instance group is available.'
            self.log_and_raise(http_status_code=500, reason=reasonErr)

        # Determine hostname of ascd_endpoint and setup the HA List
        portcolon = self.ascd_endpoint.rfind(':')
        slash = self.ascd_endpoint.find('://')
        host = self.ascd_endpoint[slash + 3:portcolon]
        HA_LIST = env['KERNEL_CONDUCTOR_HA_ENDPOINTS'].split(',')
        HA_LIST.insert(0, host)

        header = 'Accept: application/json'
        authorization = 'Authorization: Bearer %s' % jwt_token
        cookie_jar = pjoin(env['KERNEL_NOTEBOOK_DATA_DIR'], env['KERNEL_NOTEBOOK_COOKIE_JAR'])
        sslconf = env['KERNEL_CURL_SECURITY_OPT'].split()
        url = '%s/auth/logon/jwt?topology=%s' % (self.ascd_endpoint, env['KERNEL_TOPOLOGY'])
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        if 'Error' in output:
            reasonErr = 'Failed to perform JWT Auth Logon. ' + output.splitlines()[0]
            self.log.warning(cmd)
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        self.rest_credential = url_unescape(output)[1:-1]

        # Assemble EGO Token Logon REST call
        authorization = 'Authorization: PlatformToken token=' + output.strip('"')
        url = '%s/auth/logon' % self.ascd_endpoint
        cmd = ['curl', '-v', '-c', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        if 'Error' in output:
            reasonErr = 'Failed to perform EGO Auth Logon. ' + output.splitlines()[0]
            self.log.warning(cmd)
            self.log_and_raise(http_status_code=500, reason=reasonErr)

        # Get the Python path to use to make sure the right conda environment is used
        url = '%s/anaconda/instances/%s' % (self.ascd_endpoint, env['KERNEL_ANACONDA_INST_UUID'])
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        response = json.loads(output) if output else None
        if response is None or not response['parameters']['deploy_home']['value']:
            reasonErr = 'Could not retrieve anaconda instance. Verify anaconda instance with id '
            reasonErr = reasonErr + env['KERNEL_ANACONDA_INST_UUID'] + ' exists'
            self.log.warning(cmd)
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        else:
            env_dict['KERNEL_PYSPARK_PYTHON'] = response['parameters']['deploy_home']['value'] \
                + '/anaconda/envs/' + env['KERNEL_ANACONDA_ENV'] + '/bin/python'

        # Get instance group information we need
        url = '%s/instances?id=%s&fields=sparkinstancegroup,outputs' % (self.ascd_endpoint, env['KERNEL_IG_UUID'])
        cmd = ['curl', '-v', '-b', cookie_jar, '-X', 'GET', '-H', header, '-H', authorization, url]
        cmd[2:2] = sslconf
        output, stderr = self._performRestCall(cmd, url, HA_LIST)
        response = json.loads(output) if output else None

        if response is None or len(response) == 0 or response[0] is None:
            reasonErr = 'Could not retrieve instance group. Verify instance group with id ' \
                        + env['KERNEL_IG_UUID'] + ' exists.'
            self.log.warning(cmd)
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        elif response is None or response[0] is None or 'value' not in response[0]['outputs']['batch_master_rest_urls']:
            reasonErr = 'Could not retrieve outputs for instance group. Verify instance group with id ' \
                + env['KERNEL_IG_UUID'] + ' is started'
            self.log.warning(cmd)
            self.log_and_raise(http_status_code=500, reason=reasonErr)
        else:
            env_dict['KERNEL_SPARK_HOME'] = response[0]['sparkinstancegroup']['sparkhomedir']
            env_dict['KERNEL_NOTEBOOK_MASTER_REST'] = response[0]['outputs']['batch_master_rest_urls']['value']
            self.conductor_endpoint = response[0]['outputs']['one_batch_master_web_submission_url']['value']
        return response
