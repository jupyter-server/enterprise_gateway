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

logging.getLogger('paramiko').setLevel(os.getenv('ELYRA_SSH_LOG_LEVEL', logging.WARNING))

proxy_launch_log = os.getenv('ELYRA_PROXY_LAUNCH_LOG', '/var/log/jnbg/proxy_launch.log')


class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """
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


class StandaloneProcessProxy(BaseProcessProxyABC):
    # FIXME - properly deal with connection_file_dir, hosts, username and password

    remote_connection_file_dir = os.getenv('ELYRA_REMOTE_CONNECTION_DIR', '/tmp/')

    username = os.getenv('ELYRA_REMOTE_USER')
    password = os.getenv('ELYRA_REMOTE_PWD')  # this should use password-less ssh

    remote_hosts = os.getenv('ELYRA_REMOTE_HOSTS', 'localhost').split(',')
    host_index = 0

    @staticmethod
    def determine_next_host():
        next_host = StandaloneProcessProxy.remote_hosts[StandaloneProcessProxy.host_index %
                                                        StandaloneProcessProxy.remote_hosts.__len__()]
        StandaloneProcessProxy.host_index += 1
        return next_host

    pid = 0
    remote_connection_file = None

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
        self.kernel_manager.ip = gethostbyname(self.ip)  # convert to ip if host is provided
        # write out connection file - which has the remote IP - prior to copy...
        self.kernel_manager.cleanup_connection_file()
        self.kernel_manager.write_connection_file()

        cmd = self.build_startup_command(kernel_cmd)
        self.kernel_manager.log.debug('Invoking cmd: {}'.format(cmd))
        result_pid = 'bad_pid'  # purposely initialize to bad int value
        result = self.rsh(cmd, self.kernel_manager.connection_file, self.remote_connection_file)
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
        result = self.rsh(cmd)
        for line in result:
            val = line.strip()
        if val == '0':
            return None
        return False

    def cleanup(self):
        cmd = 'rm -f {}; echo $?'.format(self.remote_connection_file)
        result = self.rsh(cmd)
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

    def rsh(self, command, src_file=None, dst_file=None):
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if len(StandaloneProcessProxy.password) > 0:
                ssh.connect(self.ip, port=22, username=StandaloneProcessProxy.username,
                            password=StandaloneProcessProxy.password)
            else:
                ssh.connect(self.ip, port=22, username=StandaloneProcessProxy.username)

            if src_file is not None and dst_file is not None:
                try:
                    self.kernel_manager.log.debug("Copying file '{}' to file '{}@{}' ..."
                                                  .format(src_file, self.ip, dst_file))
                    sftp = ssh.open_sftp()
                    sftp.put(src_file, dst_file)
                except Exception as e:
                    self.kernel_manager.log.error(
                        "Exception '{}' occurred attempting to copy file '{}' "
                        "to '{}' on '{}' with user '{}', message='{}'"
                            .format(type(e).__name__, src_file, dst_file, self.ip, StandaloneProcessProxy.username, e))
                    raise e

            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()

        except Exception as e:
            self.kernel_manager.log.error(
                "Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                    .format(type(e).__name__, self.ip, StandaloneProcessProxy.username, e))
            raise e

        finally:
            if ssh is not None:
                ssh.close()

        return lines


class YarnProcessProxy(BaseProcessProxyABC):
    kernel_id = None
    application_id = None
    local_proc = None
    yarn_endpoint = os.getenv('ELYRA_YARN_ENDPOINT', 'http://localhost:8088/ws/v1/cluster')

    def __init__(self,  kernel_manager, **kw):
        super(YarnProcessProxy, self).__init__(kernel_manager, **kw)

    def launch_process(self, kernel_cmd, **kw):
        super(YarnProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.kernel_manager.log.debug("yarn env: {}".format(kw['env']))

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.kernel_manager.log.info("YarnProcessProxy.init, YARN endpoint {}, launch yarn-cluster: pid {}, cmd '{}'".format(self.yarn_endpoint, self.local_proc.pid, kernel_cmd))
        return self

    def poll(self):
        """
        Submitting a new kernel/app to YARN will take a while to be ACCEPTED.
        Thus application ID will probably not be available immediately for poll.
        So will regard the application as RUNNING when application ID not ready yet.
        :return: None if the application ID is not ready, or the app is RUNNING. Otherwise False. 
        """
        self.kernel_manager.log.debug("YarnProcessProxy.poll")
        if self.get_application_id():
            app = YarnProcessProxy.query_app_by_id(self.yarn_endpoint, self.application_id)
            if app and app.get('state', '') == 'RUNNING':
                return None
            else:
                return False
        return None

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
        self.kernel_manager.log.debug("YarnProcessProxy.kill")
        if self.get_application_id():
            YarnProcessProxy.kill_app_by_id(self.yarn_endpoint, self.application_id)
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
        """
        header = "Content-Type: application/json"
        data = '{"state": "KILLED"}'
        url = '%s/apps/%s/state' % (yarn_api_endpoint, app_id)
        cmd = ['curl', '-X', 'PUT', '-H', header, '-d', data, url]
        subprocess.Popen(cmd)
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
                self.kernel_manager.log.info("Application ID {} ready for kernel {}.".format(app['id'], self.kernel_id))
            else:
                self.kernel_manager.log.warn("Application ID not ready for kernel {}, will retry later.".format(self.kernel_id))
        return self.application_id
