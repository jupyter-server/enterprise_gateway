# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import signal
import abc
import json
import paramiko
import logging
import time
import tornado
import subprocess
from ipython_genutils.py3compat import with_metaclass
from socket import *
from jupyter_client import launch_kernel
from yarn_api_client.resource_manager import ResourceManager
from datetime import datetime

logging.getLogger('paramiko').setLevel(os.getenv('ELYRA_SSH_LOG_LEVEL', logging.WARNING))

# TODO - properly deal with environment variables - some should be promoted to properties
# Pop certain env variables that don't need to be logged, e.g. password
env_pop_list = ['ELYRA_REMOTE_PWD', 'LS_COLORS']
remote_connection_file_dir = os.getenv('ELYRA_REMOTE_CONNECTION_DIR', '/tmp/')
username = os.getenv('ELYRA_REMOTE_USER')
password = os.getenv('ELYRA_REMOTE_PWD')  # this should use password-less ssh
proxy_launch_log = os.getenv('ELYRA_PROXY_LAUNCH_LOG', '/var/log/jnbg/proxy_launch.log')
kernel_launch_timeout = float(os.getenv('ELYRA_KERNEL_LAUNCH_TIMEOUT', '30'))
max_poll_attempts = int(os.getenv('ELYRA_MAX_POLL_ATTEMPTS', '5'))
poll_interval = float(os.getenv('ELYRA_POLL_INTERVAL', '1.0'))


class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """
    remote_connection_file = None
    kernel_manager = None
    log = None
    kernel_id = None
    hosts = None

    def __init__(self, kernel_manager, **kw):
        self.kernel_manager = kernel_manager
        self.log = kernel_manager.log
        # extract the kernel_id string from the connection file and set the KERNEL_ID environment variable
        self.kernel_id = os.path.basename(self.kernel_manager.connection_file). \
            replace('kernel-', '').replace('.json', '')

        # ask the subclass for the set of applicable hosts
        self.hosts = self.get_hosts()
        # add the applicable kernel_id to the env dict
        env_dict = kw['env']
        env_dict['KERNEL_ID'] = self.kernel_id
        for k in env_pop_list:
            env_dict.pop(k, None)
        self.log.debug("BaseProcessProxy env: {}".format(kw['env']))

    @abc.abstractmethod
    def launch_process(self, cmd, **kw):
        pass

    def cleanup(self):
        pass

    def get_hosts(self):
        pass

    @abc.abstractmethod
    def poll(self):
        pass

    def wait(self):
        self.log.debug("{}.wait".format(self.__class__.__name__))
        for i in range(max_poll_attempts):
            if self.poll():
                time.sleep(poll_interval)
            else:
                break
        else:
            self.log.warning("Wait timeout of {} seconds exhausted. Continuing...".
                             format(max_poll_attempts*poll_interval))

    @abc.abstractmethod
    def send_signal(self, signum):
        pass

    @abc.abstractmethod
    def kill(self):
        pass

    def _getSSHClient(self, host):
        """
        Create a SSH Client based on host, username and password if provided.
        If there is any AuthenticationException/SSHException, raise HTTP Error 403 as permission denied.

        :param host:
        :return: ssh client instance
        """
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            host_ip = gethostbyname(host)
            if password:
                ssh.connect(host_ip, port=22, username=username, password=password)
            else:
                ssh.connect(host_ip, port=22, username=username)
        except Exception as e:
            self.log.error("Exception '{}' occurred when creating a SSHClient connecting to '{}' with user '{}', "
                            "message='{}'.".format(type(e).__name__, host, username, e))
            if e is paramiko.SSHException or paramiko.AuthenticationException:
                error_message = "Failed to authenticate SSHClient with password" + " provided" if password else "-less SSH"
                raise tornado.web.HTTPError(403, error_message)
            else:
                raise e
        return ssh

    def rsh(self, host, command, src_file=None, dst_file=None):
        ssh = self._getSSHClient(host)
        try:
            if src_file is not None and dst_file is not None:
                self.rcp(host, src_file, dst_file, ssh)
            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()
        except Exception as e:
            self.log.error("Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                .format(type(e).__name__, host, username, e))
            raise e

        finally:
            if ssh is not None:
                ssh.close()

        return lines

    def rcp(self, host, src_file, dst_file, ssh=None, pull=False):
        """ Copies src_file to dst_file.  If pull is True, the file is pulled (via get),
            else the file is pushed (via put).  If a current ssh connection is not included,
            one will be created and closed.

        :return: True if the remote copy succeeds, otherwise raise Exception.
        """
        close_connection = False
        if ssh is None:
            close_connection = True
            ssh = self._getSSHClient(host)

        msg_direction = "from" if pull else "on"
        try:
            self.log.debug("Copying file '{}' to file '{}' {} host '{}' ...".format(src_file, dst_file, msg_direction, host))
            sftp = ssh.open_sftp()
            sftp.get(src_file, dst_file) if pull else sftp.put(src_file, dst_file)
        except Exception as e:
            self.log.error("Exception '{}' occurred attempting to copy file '{}' to '{}' {} '{}' with user '{}', "
                        "message='{}'".format(type(e).__name__, src_file, dst_file, msg_direction, host, username, e))
            raise e
        finally:
            if close_connection and ssh:
                ssh.close()
        return True

    def get_connection_filename(self):
        """Allows the remote process to indicate a new connection file name - that may exist on a remote system.
           It is the remote process proxy's responsibility to ensure the file is located in the correct place.
        """
        if self.remote_connection_file is None:
            self.remote_connection_file = remote_connection_file_dir + \
                                      os.path.basename(self.kernel_manager.connection_file)
        return self.remote_connection_file


class StandaloneProcessProxy(BaseProcessProxyABC):
    host_index = 0
    pid = 0

    def __init__(self, kernel_manager, **kw):
        super(StandaloneProcessProxy, self).__init__(kernel_manager, **kw)

    def get_hosts(self):
        if self.hosts is None:
            self.hosts = os.getenv('ELYRA_REMOTE_HOSTS', 'localhost').split(',')
        return self.hosts

    def launch_process(self, kernel_cmd, **kw):
        super(StandaloneProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.ip = self.determine_next_host()

        # write out connection file - which has the remote IP - prior to copy...
        self.kernel_manager.ip = gethostbyname(self.ip)  # convert to ip if host is provided
        self.kernel_manager.cleanup_connection_file()
        self.kernel_manager.write_connection_file()

        cmd = self.build_startup_command(kernel_cmd, **kw)
        self.log.debug('Invoking cmd: {}'.format(cmd))
        result_pid = 'bad_pid'  # purposely initialize to bad int value
        result = self.rsh(self.ip, cmd, self.kernel_manager.connection_file, self.get_connection_filename())
        for line in result:
            result_pid = line.strip()

        try:
            self.pid = int(result_pid)
        except ValueError:
            raise RuntimeError("Failure occurred starting remote kernel on '{}'.  Returned result: {}"
                               .format(self.ip, result))

        # Enable the following to exercise pull-style logic...
        #self.log.debug("Testing pull connection file logic from {}@{} to {}...".
        #               format(self.ip, self.get_connection_filename(),self.kernel_manager.connection_file))
        #self.kernel_manager.cleanup_connection_file()  # remove file prior to pull
        #self.rcp(self.ip, self.get_connection_filename(), self.kernel_manager.connection_file, pull=True)
        #self.kernel_manager.load_connection_file()  # load file contents into members
        #self.kernel_manager.ip = gethostbyname(self.ip)  # force update to remote ip - not required in normal pull
        #self.kernel_manager.write_connection_file()  # write members to file so its marked as written

        self.log.info("Remote kernel launched on '{}', pid={}".format(self.kernel_manager.ip, self.pid))
        return self

    def poll(self):
        result = self.remote_signal(0)
        #  self.log.debug('StandaloneProcessProxy.poll: {}'.format(result))
        return result

    def send_signal(self, signum):
        result = self.remote_signal(signum)
        self.log.debug("StandaloneProcessProxy.send_signal({}): {}".format(signum, result))
        return result

    def kill(self):
        result = self.remote_signal(signal.SIGKILL)
        self.log.debug("StandaloneProcessProxy.kill: {}".format(result))
        return result

    def remote_signal(self, signum):
        val = None
        # Use a negative signal number to signal process group
        cmd = 'kill -{} {}; echo $?'.format(signum, self.pid)
        result = self.rsh(self.ip, cmd)
        for line in result:
            val = line.strip()
        if val == '0':
            return None
        return False

    def cleanup(self):
        val = None
        cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
        result = self.rsh(self.ip, cmd)
        for line in result:
            val = line.strip()
        if val == '0':
            return None
        return False

    def build_startup_command(self, argv_cmd, **kw):
        """
        Builds the command to invoke by concatenating envs from kernelspec followed by the kernel argvs.

        We also force nohup, redirection to a file and place in background, then follow with an echo
        for the background pid.
        """
        cmd = ''
        for key, value in self.kernel_manager.kernel_spec.env.items():
            cmd += 'export {}={};'.format(key, json.dumps(value))

        # Add additional envs not in kernelspec...
        env_dict = kw['env']

        kuser = env_dict['KERNEL_USERNAME']
        if kuser is not None:
            cmd += 'export KERNEL_USERNAME="{}";'.format(kuser)
        kid = env_dict['KERNEL_ID']
        if kid is not None:
            cmd += 'export KERNEL_ID="{}";'.format(kid)

        cmd += 'nohup'
        for arg in argv_cmd:
            cmd += ' {}'.format(arg)

        cmd += ' >> {} 2>&1 & echo $!'.format(proxy_launch_log)

        return cmd

    def determine_next_host(self):
        next_host = self.hosts[StandaloneProcessProxy.host_index % self.hosts.__len__()]
        StandaloneProcessProxy.host_index += 1
        return next_host


class YarnProcessProxy(BaseProcessProxyABC):

    application_id = None
    local_proc = None
    yarn_endpoint = os.getenv('ELYRA_YARN_ENDPOINT', 'http://localhost:8088/ws/v1/cluster')
    initial_states = {'NEW', 'SUBMITTED', 'ACCEPTED', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED'}  # Don't include FAILED state
    start_time = None
    resource_mgr = ResourceManager(serviceEndpoint=yarn_endpoint)
    pull_connection_files = False

    def __init__(self,  kernel_manager, **kw):
        super(YarnProcessProxy, self).__init__(kernel_manager, **kw)
        if kernel_manager.kernel_spec.language.lower() == 'scala':
            self.pull_connection_files = (os.getenv('ELYRA_PULL_CONNECTION_FILES', 'False') == 'True')
        elif kernel_manager.kernel_spec.language.lower() == 'python':
            self.pull_connection_files = (os.getenv('ELYRA_PULL_CONNECTION_FILES', 'True') == 'True')
        elif kernel_manager.kernel_spec.language.lower() == 'r':
            self.pull_connection_files = (os.getenv('ELYRA_PULL_CONNECTION_FILES', 'False') == 'True')

    def get_hosts(self):
        if self.hosts is None:
            self.hosts = YarnProcessProxy.query_yarn_nodes()
        return self.hosts

    def launch_process(self, kernel_cmd, **kw):
        """ Launches the Yarn process.  Prior to invocation, connection files will be distributed to each applicable
            Yarn node so that its in place when the kernel is started.  This step is skipped if pull mode is configured,
            which results in the kernel process determining ports and generating encoding key.
            Once started, the method will poll the Yarn application (after discovering the application ID via the
            kernel ID) until the application is in RUNNING state.  Note that this polling may timeout and result in
            a 503 Http error (Service unavailable).
            Once in RUNNING state, the selected host is determined.  If pull mode is configured, the remote file is 
            copied locally and member variables are loaded based on its contents.  If pull mode is not configured, the
            kernel manager's IP is updated to the selected node.
        """
        # TODO: if YARN api endpoint in HTTPS mode then all http address fields will be blank in the JSON response.
        # Since even in HTTPS mode YARN REST API call can still be issued, we'd better ensure the end point is a HTTP one.

        super(YarnProcessProxy, self).launch_process(kernel_cmd, **kw)

        if not self.pull_connection_files:
            self.distribute_connection_files()

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kw)

        self.confirm_yarn_application_startup(kernel_cmd, **kw)

        return self

    def poll(self):
        """Submitting a new kernel/app to YARN will take a while to be ACCEPTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in ACCEPTED or SUBMITTED state.

        :return: None if the application's ID is available and state is ACCEPTED/SUBMITTED/RUNNING. Otherwise False. 
        """
        state = None
        result = False

        if self.get_application_id():
            state = YarnProcessProxy.query_app_state_by_id(self.application_id)
            if state in YarnProcessProxy.initial_states:
                result = None

        self.log.debug("YarnProcessProxy.poll, application ID: {}, kernel ID: {}, state: {}".
                       format(self.application_id, self.kernel_id, state))

        return result

    def send_signal(self, signum):
        """Currently only support 0 as poll and other as kill.
        
        :param signum
        :return: 
        """
        self.log.debug("YarnProcessProxy.send_signal {}".format(signum))
        if signum == 0:
            return self.poll()
        elif signum == signal.SIGINT:
            self.log.debug("YarnProcessProxy.send_signal, SIGINT requests will be ignored")
            return self.poll()
        else:
            return self.kill()

    def kill(self):
        """Kill a kernel.
        :return: None if the application existed and is not in RUNNING state, False otherwise. 
        """
        state = None
        result = False
        if self.get_application_id():
            resp = YarnProcessProxy.kill_app_by_id(self.application_id)
            self.log.debug("YarnProcessProxy.kill_app_by_id response: {}, confirming app state is not RUNNING".format(resp))

            i, state = 1, YarnProcessProxy.query_app_state_by_id(self.application_id)
            while state not in YarnProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = YarnProcessProxy.query_app_state_by_id(self.application_id)
                i = i+1

            if state in YarnProcessProxy.final_states:
                result = None

        if self.local_proc:
            self.local_proc.kill()

        self.log.debug("YarnProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}"
                       .format(self.application_id, self.kernel_id, state))

        return result

    def cleanup(self):
        self.log.debug("Removing connection files from host(s): {}".format(self.hosts))
        for host in self.hosts:
            cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
            self.rsh(host, cmd)

        # reset application id to force new query - handles kernel restarts/interrupts
        self.application_id = None

    def distribute_connection_files(self):
        # TODO - look into the parallelizing this - only necessary on push mode
        self.log.debug("Copying connection file {} to host(s): {}".
                       format(self.kernel_manager.connection_file, self.hosts))

        for host in self.hosts:
            self.rcp(host, self.kernel_manager.connection_file, self.get_connection_filename())

    def confirm_yarn_application_startup(self, kernel_cmd, **kw):
        """ Confirms the yarn application is in a started state before returning.  Should post-RUNNING states be
            unexpectedly encountered (FINISHED, KILLED) then we must throw, otherwise the rest of the JKG will
            believe its talking to a valid kernel.
        """
        self.start_time = YarnProcessProxy.get_current_time()
        self.log.debug("YarnProcessProxy - confirm startup, Kernel ID: {}, YARN endpoint: {}, spark-submit pid {}, "
                       "cmd: '{}'".format(self.kernel_id, self.yarn_endpoint, self.local_proc.pid, kernel_cmd))
        i = 0
        app_state = None
        host = ''
        assigned_ip = ''
        need_pull_file = False
        if self.pull_connection_files:
            need_pull_file = True
            self.kernel_manager.reset_connections()
            self.log.debug("Reset connection profile {} in pull mode.".format(self.kernel_manager.connection_file))
        while app_state != 'RUNNING' or need_pull_file:
            # Ensure app in RUNNING state and if pull mode, connection file ready TODO - this needs to be revisited
            time.sleep(poll_interval)
            i += 1
            time_interval = YarnProcessProxy.get_time_diff(self.start_time, YarnProcessProxy.get_current_time())
            self.handle_timeout(time_interval, kernel_launch_timeout)

            if self.get_application_id(True):
                if app_state != 'RUNNING':
                    app_state = YarnProcessProxy.query_app_state_by_id(self.application_id)
                if host == '':
                    app = YarnProcessProxy.query_app_by_id(self.application_id)
                    if app and app.get('amHostHttpAddress'):
                        host = app.get('amHostHttpAddress').split(':')[0]
                        self.log.debug("Kernel '{}' with app ID {} has been assigned to host {}. CurrentState={}, Attempt={}"
                                  .format(self.kernel_id, self.application_id, host, app_state, i))
                        # Set the kernel manager ip to the actual host where the application landed.
                        assigned_ip = gethostbyname(host)

                if app_state in YarnProcessProxy.final_states:
                    raise tornado.web.HTTPError(500, "Kernel '{}' with Yarn application ID {} unexpectedly found in"
                        "state '{}' during kernel startup!".format(self.kernel_id, self.application_id, app_state))
                elif app_state != 'RUNNING':
                    self.log.debug("Waiting for application to enter 'RUNNING' state. "
                               "KernelID={}, ApplicationID={}, AssignedHost={}, CurrentState={}, Attempt={}".
                               format(self.kernel_id, self.application_id, host, app_state, i))
                elif self.pull_connection_files:
                    self.log.debug("Pulling connection file {} on host {} to local, ApplicationID={}, Attempt={}".
                                   format(self.get_connection_filename(), host, self.application_id, i))
                    try:
                        if self.rcp(host=host, src_file=self.get_connection_filename(), dst_file=self.kernel_manager.connection_file, pull=True):
                            need_pull_file = False
                            self.log.info("Successfully pulled '{}' from host '{}'".format(self.get_connection_filename(), host))
                            self.update_connection(assigned_ip)
                    except Exception as e:
                        if type(e) is IOError and e.errno == 2:
                            self.log.debug("No such file when pulling {} for {}, need to retry.".format(
                                self.get_connection_filename(), self.application_id))
                        else:
                            self.log.error("Exception '{}' occured when pulling connection file from host '{}', app '{}' "
                                    "Kernel ID '{}'".format(type(e).__name__, host, self.application_id, self.kernel_id))
                            self.kill()
                            raise e
                else:
                    self.update_connection(assigned_ip)

    def update_connection(self, assigned_ip):
        self.kernel_manager.load_connection_file(connection_file=self.kernel_manager.connection_file)  # load file contents into members
        self.kernel_manager.cleanup_connection_file()
        self.kernel_manager.ip = assigned_ip
        self.kernel_manager.write_connection_file()  # write members to file so its marked as written
        self.log.debug("Successfully updated the ip in connection file '{}'.".format(self.kernel_manager.connection_file))

    def handle_timeout(self, time_interval, threshold):
        if time_interval > threshold:
            timeout_message = "Application ID is None. Failed to submit a new application to YARN."
            error_http_code = 500
            if self.get_application_id(True):
                if YarnProcessProxy.query_app_state_by_id(self.application_id) != "RUNNING":
                    timeout_message = "YARN resources unavailable after {} seconds for app {}!".format(
                        time_interval, self.application_id)
                    error_http_code = 503
                elif self.pull_connection_files:
                    timeout_message = "App {} is RUNNING, but waited too long to pull connection file".format(self.application_id)
            self.kill()
            timeout_message = "Kernel {} launch timeout due to: {}".format(self.kernel_id, timeout_message)
            self.log.error(timeout_message)
            raise tornado.web.HTTPError(error_http_code, timeout_message)

    def get_application_id(self, ignore_final_states=False):
        # Return the kernel's YARN application ID if available, otherwise None.  If we're obtaining application_id
        # from scratch, do not consider kernels in final states.  TODO - may need to treat FAILED state differently.
        if not self.application_id:
            app = YarnProcessProxy.query_app_by_name(self.kernel_id)
            state_condition = True
            if app and ignore_final_states:
                state_condition = app.get('state') not in YarnProcessProxy.final_states

            if app and len(app.get('id', '')) > 0 and state_condition:
                self.application_id = app['id']
                time_interval = YarnProcessProxy.get_time_diff(self.start_time, YarnProcessProxy.get_current_time())
                self.log.info("Application ID: {} assigned for kernel: {}, state: {}, {} seconds after starting."
                              .format(app['id'], self.kernel_id, app.get('state'), time_interval))
            else:
                self.log.info("Application ID not yet assigned for kernel: {}, will retry later.".format(self.kernel_id))
        return self.application_id

    @staticmethod
    def query_app_by_name(kernel_id):
        """Retrieve application by using kernel_id as the unique app name.
        When submit a new app, it may take a while for YARN to accept and run and generate the application ID.
        Note: if a kernel restarts with the same kernel id as app name, multiple applications will be returned.
        For now, the app/kernel with the top most application ID will be returned as the target app, assuming the app
        ID will be incremented automatically on the YARN side.

        :param kernel_id: as the unique app name for query
        :return: The JSON object of an application. 
        """
        top_most_app_id = ''
        target_app = None
        data = YarnProcessProxy.resource_mgr.cluster_applications().data
        if data and 'apps' in data and 'app' in data['apps']:
            for app in data['apps']['app']:
                if app.get('name', '').find(kernel_id) >= 0 and app.get('id') > top_most_app_id:
                    target_app = app
                    top_most_app_id = app.get('id')
        return target_app

    @staticmethod
    def query_yarn_nodes():
        """Retrieve all nodes host name in a YARN cluster.
        
        :return: A list of "nodeHostName" from JSON object
        """
        data = YarnProcessProxy.resource_mgr.cluster_nodes().data
        nodes_list = list([])
        if data and 'nodes' in data and 'node' in data['nodes']:
            for node in data['nodes']['node']:
                nodes_list.append(node['nodeHostName'])
        return nodes_list

    @staticmethod
    def query_app_by_id(app_id):
        """Retrieve an application by application ID.

        :param app_id
        :return: The JSON object of an application.
        """
        data = YarnProcessProxy.resource_mgr.cluster_application(application_id=app_id).data
        if data and 'app' in data:
            return data['app']
        return None

    @staticmethod
    def query_app_state_by_id(app_id):
        """Return the state of an application.

        :param app_id: 
        :return: 
        """
        url = '%s/apps/%s/state' % (YarnProcessProxy.yarn_endpoint, app_id)
        cmd = ['curl', '-X', 'GET', url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = process.communicate()
        return json.loads(output).get('state') if output else None

    @staticmethod
    def kill_app_by_id(app_id):
        """Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.
        TODO: extend the yarn_api_client to support cluster_application_kill with PUT, e.g.:
            YarnProcessProxy.resource_mgr.cluster_application_kill(application_id=app_id)

        :param app_id 
        :return: The JSON response of killing the application.
        """
        header = "Content-Type: application/json"
        data = '{"state": "KILLED"}'
        url = '%s/apps/%s/state' % (YarnProcessProxy.yarn_endpoint, app_id)
        cmd = ['curl', '-X', 'PUT', '-H', header, '-d', data, url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = process.communicate()
        return json.loads(output) if output else None

    @staticmethod
    def get_current_time():
        # Return the current time stamp in milliseconds.
        return str(datetime.now())[:-2]

    @staticmethod
    def get_time_diff(time_str1, time_str2):
        # Return the difference between two timestamps in seconds (with milliseconds).
        time_format = "%Y-%m-%d %H:%M:%S.%f"
        time1, time2 = datetime.strptime(time_str1, time_format), datetime.strptime(time_str2, time_format)
        diff = max(time1, time2) - min(time1, time2)
        return float("%d.%d" % (diff.seconds, diff.microseconds / 1000))
