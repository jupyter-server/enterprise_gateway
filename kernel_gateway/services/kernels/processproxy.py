# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import signal
import abc
import json
import socket
import paramiko
import logging
import time
import subprocess
from ipython_genutils.py3compat import with_metaclass
from socket import *
from jupyter_client import launch_kernel
from yarn_api_client.resource_manager import ResourceManager
from datetime import datetime

logging.getLogger('paramiko').setLevel(os.getenv('ELYRA_SSH_LOG_LEVEL', logging.WARNING))

proxy_launch_log = os.getenv('ELYRA_PROXY_LAUNCH_LOG', '/var/log/jnbg/proxy_launch.log')


class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """

    # FIXME - properly deal with connection_file_dir, hosts, username and password
    remote_connection_file_dir = os.getenv('ELYRA_REMOTE_CONNECTION_DIR', '/tmp/')

    username = os.getenv('ELYRA_REMOTE_USER')
    password = os.getenv('ELYRA_REMOTE_PWD', '')  # this should use password-less ssh

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
        self.hosts = self.get_hosts()

    @abc.abstractmethod
    def launch_process(self, cmd, **kw):
        env_dict = kw['env']
        env_dict['KERNEL_ID'] = self.kernel_id

        self.log.debug("BaseProcessProxy env: {}".format(kw['env']))

        return self

    def cleanup(self):
        pass

    def get_hosts(self):
        pass

    @abc.abstractmethod
    def poll(self):
        pass

    def wait(self):
        self.log.debug("{}.wait".format(self.__class__.__name__))
        poll_interval = 0.2
        wait_time = 5.0
        for i in range(int(wait_time / poll_interval)):
            if self.poll():
                time.sleep(poll_interval)
            else:
                break
        else:
            self.log.warning("Wait timeout of 5 seconds exhausted. Continuing...")

    @abc.abstractmethod
    def send_signal(self, signum):
        pass

    @abc.abstractmethod
    def kill(self):
        pass

    def rsh(self, host, command, src_file=None, dst_file=None):
        ssh = None
        host_ip = gethostbyname(host)
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if len(StandaloneProcessProxy.password) > 0:
                ssh.connect(host_ip, port=22, username=StandaloneProcessProxy.username,
                            password=StandaloneProcessProxy.password)
            else:
                ssh.connect(host_ip, port=22, username=StandaloneProcessProxy.username)

            if src_file is not None and dst_file is not None:
                self.rcp(host, src_file, dst_file, ssh)

            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()

        except Exception as e:
            self.log.error(
                "Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                .format(type(e).__name__, host_ip, StandaloneProcessProxy.username, e))
            raise e

        finally:
            if ssh is not None:
                ssh.close()

        return lines

    def rcp(self, host, src_file, dst_file, ssh=None):

        close_connection = False
        host_ip = gethostbyname(host)

        if ssh is None:
            close_connection = True
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if len(StandaloneProcessProxy.password) > 0:
                self.log.debug("Establishing a SSH connection with password.")
                ssh.connect(host_ip, port=22, username=StandaloneProcessProxy.username,
                            password=StandaloneProcessProxy.password)
            else:
                self.log.debug("Establishing a SSH connection without password.")
                ssh.connect(host_ip, port=22, username=StandaloneProcessProxy.username)
        except Exception as e:
            self.log.error(
                "Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                .format(type(e).__name__, host_ip, StandaloneProcessProxy.username, e))
            raise e

        try:
            self.log.debug("Copying file '{}' to file '{}@{}' ...".format(src_file, host_ip, dst_file))
            sftp = ssh.open_sftp()
            sftp.put(src_file, dst_file)
        except Exception as e:
            self.log.error(
                "Exception '{}' occurred attempting to copy file '{}' "
                "to '{}' on '{}' with user '{}', message='{}'"
                .format(type(e).__name__, src_file, dst_file, host_ip, StandaloneProcessProxy.username, e))
            raise e

        if close_connection:
            if ssh is not None:
                ssh.close()

    def get_connection_filename(self):
        """Allows the remote process to indicate a new connection file name - that may exist on a remote system.
           It is the remote process proxy's responsibility to ensure the file is located in the correct place.
        """
        if self.remote_connection_file is None:
            self.remote_connection_file = BaseProcessProxyABC.remote_connection_file_dir + \
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

        cmd = self.build_startup_command(kernel_cmd)
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
        cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
        result = self.rsh(self.ip, cmd)
        for line in result:
            val = line.strip()
        if val == '0':
            return None
        return False

    def build_startup_command(self, argv_cmd):
        """
        Builds the command to invoke by concatenating envs from kernelspec followed by the kernel argvs.

        We also force nohup, redirection to a file and place in background, then follow with an echo
        for the background pid.
        """
        cmd = ''
        for key, value in self.kernel_manager.kernel_spec.env.items():
            cmd += 'export {}={};'.format(key, json.dumps(value))

        # Add additional envs not in kernelspec...
        username = os.getenv('KERNEL_USERNAME')
        if username is not None:
            cmd += 'export KERNEL_USERNAME="{}";'.format(username)
        if self.kernel_id is not None:
            cmd += 'export KERNEL_ID="{}";'.format(self.kernel_id)

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
    kernel_id = None
    application_id = None
    local_proc = None
    yarn_endpoint = os.getenv('ELYRA_YARN_ENDPOINT', 'http://localhost:8088/ws/v1/cluster')
    max_retries_span = int(os.getenv('ELYRA_YARN_MAX_RETRIES_SPAN', 5))
    retry_interval = float(os.getenv('ELYRA_YARN_RETRY_INTERVAL', 0.2))
    initial_states = set(["NEW", "SUBMITTED", "ACCEPTED", "RUNNING"])
    final_states = set(["FINISHED", "KILLED"])  # Don't include FAILED state
    yarn_app = None
    start_time = None

    def __init__(self,  kernel_manager, **kw):
        super(YarnProcessProxy, self).__init__(kernel_manager, **kw)

    def get_hosts(self):
        if self.hosts is None:
            self.hosts = YarnProcessProxy.query_yarn_nodes(self.yarn_endpoint)
        return self.hosts

    def launch_process(self, kernel_cmd, **kw):
        """Prior to starting the process, copy the connection file to every YARN node.
        This is to avoid having to detect where the kernel application was moved to (which would be too late)
        because each YARN node is likely to be the host of a kernel.
        Note we need to write a new connection file so that that connection file has the IP of the host that serving a kernel.
        Once launched we'll circle back and do this one final time relative to the host where the application landed.
        To do so need to ensure application ID ready during launching, and once obtained, query YARN for the host address.

        TODO: if YARN api endpoint in HTTPS mode then all http address fields will be blank in the JSON response.
        """
        super(YarnProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.distribute_connection_files()

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kw)

        # confirm yarn application is in RUNNING state
        self.confirm_yarn_application_startup(kernel_cmd, **kw)

        return self

    def poll(self):
        """Submitting a new kernel/app to YARN will take a while to be ACCEPTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID still in ACCEPTED or SUBMITTED state.
        TODO: If due to resources issue a kernel in ACCEPTED state for too long, may regard it as a dead kernel and restart/kill.

        :return: None if the application's ID is available and state is ACCEPTED/SUBMITTED/RUNNING. Otherwise False. 
        """
        state = None
        result = False
        if self.get_application_id():
            state = YarnProcessProxy.query_app_state_by_id(self.yarn_endpoint, self.application_id)
            if state in YarnProcessProxy.initial_states:
                result = None

        self.log.debug("YarnProcessProxy.poll, application ID: {}, kernel ID: {}, state: {}"
                        .format(self.application_id, self.kernel_id, state))

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
            resp = YarnProcessProxy.kill_app_by_id(self.yarn_endpoint, self.application_id)
            self.log.debug("YarnProcessProxy.kill_app_by_id response: {}, confirming app state is not RUNNING".format(resp))

            i, state = 1, YarnProcessProxy.query_app_state_by_id(self.yarn_endpoint, self.application_id)
            while state not in YarnProcessProxy.final_states and i <= YarnProcessProxy.max_retries_span:
                delay = min(YarnProcessProxy.retry_interval * i, 1.0)
                time.sleep(delay)
                state = YarnProcessProxy.query_app_state_by_id(self.yarn_endpoint, self.application_id)
                i = i+1

            if state in YarnProcessProxy.final_states:
                result = None

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
        # FIXME - look into the parallelizing this.  Note: That requires a means of making each of
        # newly written files independent of each other
        self.log.debug("Copying connection file {} to host(s): {}".
                       format(self.kernel_manager.connection_file, self.hosts))
        for host in self.hosts:
            self.kernel_manager.ip = gethostbyname(host)
            self.kernel_manager.cleanup_connection_file()
            self.kernel_manager.write_connection_file()
            self.rcp(host, self.kernel_manager.connection_file, self.get_connection_filename())
            self.log.debug("Connection file copied to host {}.".format(host))

    def confirm_yarn_application_startup(self, kernel_cmd, **kw):
        """ Confirms the yarn application is in a started state before returning.  Should post-RUNNING states be
            unexpectedly encountered (FINISHED, KILLED) then we must throw, otherwise the rest of the JKG will
            believe its talking to a valid kernel (FIXME - confirm this).
        """
        self.start_time = YarnProcessProxy.get_current_time()
        self.log.debug("YarnProcessProxy.launch_process, YARN endpoint: {}, spark-submit: pid {}, cmd: '{}'".
                       format(self.yarn_endpoint, self.local_proc.pid, kernel_cmd))
        i, total = 1, 0.0
        app_state = None
        host = ''
        while host == '' or app_state != 'RUNNING':  # Require running state for exit.  FIXME - this needs to be revisited
            delay = min(YarnProcessProxy.retry_interval * i, 1.0)
            time.sleep(delay)
            total += delay

            self.get_application_id(True)
            if self.application_id:

                self.yarn_app = YarnProcessProxy.query_app_by_id(self.yarn_endpoint, self.application_id)
                if self.yarn_app:
                    if host == '':
                        host = self.yarn_app.get('amHostHttpAddress', '').split(':')[0]
                        self.log.debug("Kernel {} assigned to host {}".format(self.kernel_id, host))
                        # Then set the kernel manager ip to the actual host where the application landed.
                        self.kernel_manager.ip = gethostbyname(host)
                        self.kernel_manager.cleanup_connection_file()
                        self.kernel_manager.write_connection_file()

                    app_state = self.yarn_app.get('state', '')

            self.log.debug("Waiting for application to enter 'RUNNING' state. "
                           "ID={}, AssignedHost={}, CurrentState={}, Attempt={}".
                           format(self.application_id, host, app_state, i))

            if app_state in YarnProcessProxy.final_states:
                self.log.error("Yarn application {} unexpectedly found in state '{}' during kernel startup!".
                               format(self.application_id, app_state))
                raise RuntimeError("Yarn application {} unexpectedly found in state '{}' during kernel startup!".
                               format(self.application_id, app_state))
            i += 1
        self.is_restart = False

    def get_application_id(self, ignore_final_states=False):
        # Return the kernel's YARN application ID if available, otherwise None.  If we're obtaining application_id
        # from scratch, do not consider kernels in final states.  FIXME - may need to treat FAILED state differently.
        if not self.application_id:
            app = YarnProcessProxy.query_app_by_name(self.yarn_endpoint, self.kernel_id)
            state_condition = True
            if app and ignore_final_states:
                state_condition = app.get('state','') not in YarnProcessProxy.final_states

            if app and len(app.get('id', '')) > 0 and state_condition:
                self.application_id = app['id']
                time_interval = YarnProcessProxy.get_time_diff(self.start_time, YarnProcessProxy.get_current_time())
                self.log.info("Application ID: {} ready for kernel: {}, state: {}, {} seconds after starting."
                              .format(app['id'], self.kernel_id, app.get('state',''), time_interval))
            else:
                self.log.warn("Application ID not ready for kernel: {}, will retry later.".format(self.kernel_id))
        return self.application_id

    @staticmethod
    def query_app_by_name(yarn_api_endpoint, kernel_id):
        """Retrieve application by using kernel_id as the unique app name.
        When submit a new app, it may take a while for YARN to accept and run and generate the application ID.
        Note: if a kernel restarts with the same kernel id as app name, multiple applications will be returned.
        For now, the app/kernel with the top most application ID will be returned as the target app, assuming the app
        ID will be incremented automatically on the YARN side.

        :param yarn_api_endpoint
        :param kernel_id: as the unique app name for query
        :return: The JSON object of an application. 
        """
        top_most_app_id = ''
        target_app = None
        resource_mgr = ResourceManager(serviceEndpoint=yarn_api_endpoint)
        data = resource_mgr.cluster_applications().data
        if data and 'apps' in data and 'app' in data['apps']:
            for app in data['apps']['app']:
                if app.get('name', '').find(kernel_id) >= 0 and app.get('id', '') > top_most_app_id:
                    target_app = app
                    top_most_app_id = app.get('id','')
        return target_app

    @staticmethod
    def query_yarn_nodes(yarn_api_endpoint):
        """Retrieve all nodes host name in a YARN cluster.
        
        :param yarn_api_endpoint: 
        :return: A list of "nodeHostName" from JSON object
        """
        resource_mgr = ResourceManager(serviceEndpoint=yarn_api_endpoint)
        data = resource_mgr.cluster_nodes().data
        nodes_list = list([])
        if data and 'nodes' in data:
            for node in data['nodes'].get('node', None):
                nodes_list.append(node['nodeHostName'])
        return nodes_list

    @staticmethod
    def query_app_by_id(yarn_api_endpoint, app_id):
        """Retrieve an application by application ID.

        :param yarn_api_endpoint
        :param app_id
        :return: The JSON object of an application.
        """
        resource_mgr = ResourceManager(serviceEndpoint=yarn_api_endpoint)
        data = resource_mgr.cluster_application(application_id=app_id).data
        if data and 'app' in data:
            return data['app']
        return None

    @staticmethod
    def query_app_state_by_id(yarn_api_endpoint, app_id):
        """Return the state of an application.

        :param yarn_api_endpoint: 
        :param app_id: 
        :return: 
        """
        url = '%s/apps/%s/state' % (yarn_api_endpoint, app_id)
        cmd = ['curl', '-X', 'GET', url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, stderr = process.communicate()
        return json.loads(output).get('state', '') if output else None

    @staticmethod
    def kill_app_by_id(yarn_api_endpoint, app_id):
        """Kill an application. If the app's state is FINISHED or FAILED, it won't be changed to KILLED.
        TODO: extend the yarn_api_client to support cluster_application_kill with PUT, e.g.:
            resource_mgr = ResourceManager(serviceEndpoint=yarn_endpoint)
            resource_mgr.cluster_application_kill(application_id=app_id)

        :param yarn_api_endpoint
        :param app_id 
        :return: The JSON response of killing the application.
        """
        header = "Content-Type: application/json"
        data = '{"state": "KILLED"}'
        url = '%s/apps/%s/state' % (yarn_api_endpoint, app_id)
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
        # Return the difference between two timestamps in milliseconds.
        time_format = "%Y-%m-%d %H:%M:%S.%f"
        time1, time2 = datetime.strptime(time_str1, time_format), datetime.strptime(time_str2, time_format)
        diff = max(time1, time2) - min(time1, time2)
        return diff.seconds
