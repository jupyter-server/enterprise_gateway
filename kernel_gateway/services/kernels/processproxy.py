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
from time import gmtime, strftime
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

    remote_hosts = os.getenv('ELYRA_REMOTE_HOSTS', 'localhost').split(',')
    host_index = 0

    @staticmethod
    def determine_next_host():
        next_host = BaseProcessProxyABC.remote_hosts[StandaloneProcessProxy.host_index %
                                                        StandaloneProcessProxy.remote_hosts.__len__()]
        StandaloneProcessProxy.host_index += 1
        return next_host

    remote_connection_file = None
    kernel_manager = None
    kernel_id = None

    def __init__(self, kernel_manager, **kw):
        self.kernel_manager = kernel_manager

    def launch_process(self, cmd, **kw):
        # extract the kernel_id string from the connection file and set the KERNEL_ID environment variable
        self.kernel_id = os.path.basename(self.kernel_manager.connection_file). \
            replace('kernel-', '').replace('.json', '')
        env = kw['env']
        env['KERNEL_ID'] = self.kernel_id
        return self

    def get_connection_filename(self):
        """Allows the remote process to indicate a new connection file name - that may exist on a remote system.
           It is the remote process proxy's responsibility to ensure the file is located in the correct place.
           By default, we return what's already set.
        """
        return self.kernel_manager.connection_file

    def cleanup(self):
        pass

    @abc.abstractmethod
    def poll(self):
        pass

    def wait(self):
        self.kernel_manager.log.debug("{}.wait".format(self.__class__.__name__))
        poll_interval = 0.2
        wait_time = 5.0
        for i in range(int(wait_time / poll_interval)):
            if self.poll():
                time.sleep(poll_interval)
            else:
                break
        else:
            self.kernel_manager.log.warning("Wait timeout of 5 seconds exhausted. Continuing...")

    @abc.abstractmethod
    def send_signal(self, signum):
        pass

    @abc.abstractmethod
    def kill(self):
        pass

    def rsh(self, host, command, src_file=None, dst_file=None):
        ssh = None
        ip = gethostbyname(host)
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if len(StandaloneProcessProxy.password) > 0:
                ssh.connect(ip, port=22, username=StandaloneProcessProxy.username,
                            password=StandaloneProcessProxy.password)
            else:
                ssh.connect(ip, port=22, username=StandaloneProcessProxy.username)

            if src_file is not None and dst_file is not None:
                self.rcp(host, src_file, dst_file, ssh)

            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()

        except Exception as e:
            self.kernel_manager.log.error(
                "Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                .format(type(e).__name__, ip, StandaloneProcessProxy.username, e))
            raise e

        finally:
            if ssh is not None:
                ssh.close()

        return lines

    def rcp(self, host, src_file, dst_file, ssh=None):

        close_connection = False
        ip = gethostbyname(host)

        if ssh is None:
            close_connection = True
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if len(StandaloneProcessProxy.password) > 0:
                self.kernel_manager.log.debug("Establishing a SSH connection with password.")
                ssh.connect(ip, port=22, username=StandaloneProcessProxy.username,
                            password=StandaloneProcessProxy.password)
            else:
                self.kernel_manager.log.debug("Establishing a SSH connection without password.")
                ssh.connect(ip, port=22, username=StandaloneProcessProxy.username)
        except Exception as e:
            self.kernel_manager.log.error(
                "Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                .format(type(e).__name__, ip, StandaloneProcessProxy.username, e))
            raise e

        try:
            self.kernel_manager.log.debug("Copying file '{}' to file '{}@{}' ..."
                                          .format(src_file, ip, dst_file))
            sftp = ssh.open_sftp()
            sftp.put(src_file, dst_file)
        except Exception as e:
            self.kernel_manager.log.error(
                "Exception '{}' occurred attempting to copy file '{}' "
                "to '{}' on '{}' with user '{}', message='{}'"
                .format(type(e).__name__, src_file, dst_file, self.ip, StandaloneProcessProxy.username, e))
            raise e

        if close_connection:
            if ssh is not None:
                ssh.close()


class StandaloneProcessProxy(BaseProcessProxyABC):

    pid = 0

    def __init__(self, kernel_manager, **kw):
        super(StandaloneProcessProxy, self).__init__(kernel_manager, **kw)

    def get_connection_filename(self):
        """Allows the remote process to indicate a new connection file name - that may exist on a remote system.
           It is the remote process proxy's responsibility to ensure the file is located in the correct place.
        """
        self.remote_connection_file = StandaloneProcessProxy.remote_connection_file_dir + \
                                      os.path.basename(self.kernel_manager.connection_file)
        return self.remote_connection_file

    def launch_process(self, kernel_cmd, **kw):
        super(StandaloneProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.ip = StandaloneProcessProxy.determine_next_host()
        # write out connection file - which has the remote IP - prior to copy...
        self.kernel_manager.ip = gethostbyname(self.ip)  # convert to ip if host is provided
        self.kernel_manager.cleanup_connection_file()
        self.kernel_manager.write_connection_file()

        cmd = self.build_startup_command(kernel_cmd)
        self.kernel_manager.log.debug('Invoking cmd: {}'.format(cmd))
        result_pid = 'bad_pid'  # purposely initialize to bad int value
        result = self.rsh(self.ip, cmd, self.kernel_manager.connection_file, self.remote_connection_file)
        for line in result:
            result_pid = line.strip()

        try:
            self.pid = int(result_pid)
        except ValueError:
            raise RuntimeError("Failure occurred starting remote kernel on '{}'.  Returned result: {}"
                               .format(self.ip, result))

        self.kernel_manager.log.info("Remote kernel launched on '{}', pid={}"
                                     .format(self.kernel_manager.ip, self.pid))
        return self

    def poll(self):
        result = self.remote_signal(0)
        #  self.kernel_manager.log.debug('StandaloneProcessProxy.poll: {}'.format(result))
        return result

    def send_signal(self, signum):
        result = self.remote_signal(signum)
        self.kernel_manager.log.debug("StandaloneProcessProxy.send_signal({}): {}".format(signum, result))
        return result

    def kill(self):
        result = self.remote_signal(signal.SIGKILL)
        self.kernel_manager.log.debug("StandaloneProcessProxy.kill: {}".format(result))
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
        cmd = 'rm -f {}; echo $?'.format(self.remote_connection_file)
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


class YarnProcessProxy(BaseProcessProxyABC):
    kernel_id = None
    application_id = None
    local_proc = None
    yarn_endpoint = os.getenv('ELYRA_YARN_ENDPOINT', 'http://localhost:8088/ws/v1/cluster')
    max_retries_span = int(os.getenv('ELYRA_YARN_MAX_RETRIES_SPAN', 5))
    retry_interval = float(os.getenv('ELYRA_YARN_RETRY_INTERVAL', 0.2))
    yarn_app = None
    start_time = None

    def __init__(self,  kernel_manager, **kw):
        super(YarnProcessProxy, self).__init__(kernel_manager, **kw)

    def get_connection_filename(self):
        """Allows the remote process to indicate a new connection file name - that may exist on a remote system.
           It is the remote process proxy's responsibility to ensure the file is located in the correct place.
        """
        self.remote_connection_file = StandaloneProcessProxy.remote_connection_file_dir + \
                                      os.path.basename(self.kernel_manager.connection_file)
        return self.remote_connection_file

    def launch_process(self, kernel_cmd, **kw):
        super(YarnProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.kernel_manager.log.debug("yarn env: {}".format(kw['env']))

        # Prior to starting the process, we need to copy the connection file to each of the possible nodes.  For
        # now, that set of possible nodes is specified in the REMOTE_HOSTS environment variable (FIXME).
        # This is done to avoid having to detect where the kernel application was moved to (which would be too late).
        # Note, we need to write a new connection file so that that connection has the IP of the host that its
        # serving.  Once launched we'll circle back and do this one final time relative to the host where
        # the application landed.
        BaseProcessProxyABC.remote_hosts = YarnProcessProxy.query_yarn_nodes(self.yarn_endpoint)
        self.kernel_manager.log.debug("scp connection file {} to node(s)".format(self.kernel_manager.connection_file))
        remote_hosts = BaseProcessProxyABC.remote_hosts
        for host in remote_hosts:
            self.kernel_manager.ip = gethostbyname(host)  # convert to ip if host is provided
            self.kernel_manager.cleanup_connection_file()
            self.kernel_manager.write_connection_file()
            self.rcp(host, self.kernel_manager.connection_file, self.remote_connection_file)
            self.kernel_manager.log.debug("scp connection file to host {} finished".format(host))

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.start_time = YarnProcessProxy.get_current_time()
        self.kernel_manager.log.debug("YarnProcessProxy.init starting at {}".format(self.start_time))
        self.kernel_manager.log.info("YarnProcessProxy.init, YARN endpoint {}, launch yarn-cluster: pid {}, cmd '{}'".format(self.yarn_endpoint, self.local_proc.pid, kernel_cmd))
        # Ensure application ID ready during launching
        i, total = 1, 0.0
        while self.get_application_id() is None and total <= self.max_retries_span:
                time.sleep(self.retry_interval * i)
                total += self.retry_interval * i
                i += 1
        if self.application_id:
            self.kernel_manager.log.debug("Application ID ready during launching.")
            # Once the Yarn Application Id obtained, query for the host address.
            # TODO if HTTPS mode then all http address fields will be blank in JSON response
            self.yarn_app = YarnProcessProxy.query_app_by_id(self.yarn_endpoint, self.application_id)
            if self.yarn_app:
                host = self.yarn_app.get('amHostHttpAddress', '').split(':')[0]
                self.kernel_manager.log.debug("Kernel {} running on host {}".format(self.kernel_id, host))
                # Then set the kernel manager ip to the actual host where the application landed.
                self.kernel_manager.ip = gethostbyname(host)
                self.kernel_manager.cleanup_connection_file()
                self.kernel_manager.write_connection_file()
        else:
            self.kernel_manager.log.info("Application ID not ready during launching, with {} tries in {} seconds.".format(i, self.max_retries_span))

        return self

    def poll(self):
        """
        Submitting a new kernel/app to YARN will take a while to be ACCEPTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID not ready yet.
        :return: None if the application ID is not ready, or the app is RUNNING. Otherwise False. 
        """
        current_time = YarnProcessProxy.get_current_time()
        self.kernel_manager.log.debug("YarnProcessProxy.poll starting at {}".format(current_time))
        result = None
        if self.get_application_id():
            running_state = set(["SUBMITTED", "ACCEPTED", "RUNNING"])
            app = YarnProcessProxy.query_app_by_id(self.yarn_endpoint, self.application_id)
            if app: # for current implementation, TODO: if app is None should also return False
                if app.get('state', '') not in running_state:
                    result = False
        time_diff = YarnProcessProxy.get_time_diff(current_time, YarnProcessProxy.get_current_time())
        self.kernel_manager.log.debug("YarnProcessProxy.poll ending after {} seconds".format(time_diff))
        return result

    def send_signal(self, signum=9):
        """
        Currently only support 0 as poll and other as kill.
        :param signum
        :return: 
        """
        self.kernel_manager.log.debug("YarnProcessProxy.send_signal {}".format(signum))
        if signum == 0:
            self.kernel_manager.log.info("YarnProcessProxy.send_signal call poll")
            return self.poll()
        else:
            self.kernel_manager.log.warn("YarnProcessProxy.send_signal call kill")
            is_killed = self.kill()
            if is_killed is None:
                self.kernel_manager.log.debug("Kernel {} is killed.".format(self.kernel_id))
            else:
                self.kernel_manager.log.debug("Kernel {} is not killed.".format(self.kernel_id))
            return is_killed

    def kill(self):
        self.kernel_manager.log.debug("YarnProcessProxy.kill at {}".format(YarnProcessProxy.get_current_time()))
        if self.get_application_id():
            resp = YarnProcessProxy.kill_app_by_id(self.yarn_endpoint, self.application_id)
            self.kernel_manager.log.debug("YarnProcessProxy.kill response: {}".format(resp))
            app = YarnProcessProxy.query_app_by_id(self.yarn_endpoint, self.application_id)
            if app and app.get('state', '') != 'RUNNING':
                return None
        return False

    @staticmethod
    def query_app_by_name(yarn_api_endpoint, kernel_id, pause_time=1):
        """
        Retrieve application by using app name as the key.
        When submit a new app, it may take a while for YARN to accept and run and generate the application ID.

        :param yarn_api_endpoint
        :param kernel_id: kernel id as the app name for query
        :param pause_time: Time interval between each retry.
        :return: The JSON object of an application. 
        """
        resource_mgr = ResourceManager(serviceEndpoint=yarn_api_endpoint)
        data = resource_mgr.cluster_applications().data
        if data and 'apps' in data and 'app' in data['apps']:
            for app in data['apps']['app']:
                if app.get('name', '').find(kernel_id) >= 0:
                    return app
        time.sleep(pause_time)
        return None

    @staticmethod
    def query_yarn_nodes(yarn_api_endpoint):
        """
        Retrieve all nodes host name in a YARN cluster.
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
        """
        Retrieve an application by application ID.

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
    def kill_app_by_id(yarn_api_endpoint, app_id):
        """
        Kill an application. If the app's state is FINISHED or FAILED, will not be 
        changed as KILLED.

        :param yarn_api_endpoint
        :param app_id 
        :return: The response of killing
        """
        header = "Content-Type: application/json"
        data = '{"state": "KILLED"}'
        url = '%s/apps/%s/state' % (yarn_api_endpoint, app_id)
        cmd = ['curl', '-X', 'PUT', '-H', header, '-d', data, url]
        return subprocess.Popen(cmd)
        # TODO: extend the yarn_api_client to support cluster_application_kill with PUT
        # resource_mgr = ResourceManager(serviceEndpoint=yarn_endpoint)
        # resource_mgr.cluster_application_kill(application_id=app_id)

    def get_application_id(self):
        """
        :return: Application ID if it is available, otherwise None.
        """
        if not self.application_id:
            app = YarnProcessProxy.query_app_by_name(self.yarn_endpoint, self.kernel_id)
            if app and len(app.get('id', '')) > 0:
                self.application_id = app['id']
                time_interval = YarnProcessProxy.get_time_diff(self.start_time, YarnProcessProxy.get_current_time())
                self.kernel_manager.log.info("Application ID {} ready for kernel {}, {} seconds after starting.".format(app['id'], self.kernel_id, time_interval))
            else:
                self.kernel_manager.log.warn("Application ID not ready for kernel {}, will retry later.".format(self.kernel_id))
        return self.application_id

    @staticmethod
    def get_current_time(time_format="%Y-%m-%d %H:%M:%S"):
        # utility method
        return strftime(time_format, gmtime())

    @staticmethod
    def get_time_diff(time_str1, time_str2, time_format="%Y-%m-%d %H:%M:%S"):
        time1, time2 = datetime.strptime(time_str1, time_format), datetime.strptime(time_str2, time_format)
        diff = max(time1, time2) - min(time1, time2)
        return diff.seconds

