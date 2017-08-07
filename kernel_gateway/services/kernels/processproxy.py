# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import errno
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
from jupyter_client import launch_kernel, localinterfaces
from yarn_api_client.resource_manager import ResourceManager
from datetime import datetime
from urlparse import urlparse

# Default logging level of paramiko produces too much noise - raise to warning only.
logging.getLogger('paramiko').setLevel(os.getenv('ELYRA_SSH_LOG_LEVEL', logging.WARNING))

# TODO - properly deal with environment variables - some should be promoted to properties

# Pop certain env variables that don't need to be logged, e.g. password
env_pop_list = ['ELYRA_REMOTE_PWD', 'LS_COLORS']
username = os.getenv('ELYRA_REMOTE_USER')
password = os.getenv('ELYRA_REMOTE_PWD')  # this should use password-less ssh
proxy_launch_log = os.getenv('ELYRA_PROXY_LAUNCH_LOG', '/var/log/elyra/proxy_launch.log')
elyra_kernel_launch_timeout = float(os.getenv('ELYRA_KERNEL_LAUNCH_TIMEOUT', '30'))
max_poll_attempts = int(os.getenv('ELYRA_MAX_POLL_ATTEMPTS', '10'))
poll_interval = float(os.getenv('ELYRA_POLL_INTERVAL', '0.5'))
socket_timeout = float(os.getenv('ELYRA_SOCKET_TIMEOUT', '5.0'))

local_ip = localinterfaces.public_ips()[0]

class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """

    def __init__(self, kernel_manager):
        self.kernel_manager = kernel_manager
        # use the zero-ip from the start, can prevent having to write out connection file again
        self.kernel_manager.ip = '0.0.0.0'
        self.log = kernel_manager.log
        # extract the kernel_id string from the connection file and set the KERNEL_ID environment variable
        self.kernel_id = os.path.basename(self.kernel_manager.connection_file). \
            replace('kernel-', '').replace('.json', '')

        # Represents the local process (from popen) if applicable.  Note that we could have local_proc = None even when
        # the subclass is a LocalProcessProxy (or YarnProcessProxy).  This will happen if the JKG is restarted and the
        # persisted kernel-sessions indicate that its now running on a different server.  In those case, we use the ip
        # member variable to determine if the persisted state is local or remote and use signals with the pid to
        # implement the poll, kill and send_signal methods.
        self.local_proc = None
        self.ip = None
        self.pid = 0

    @abc.abstractmethod
    def launch_process(self, cmd, **kw):
        env_dict = kw.get('env')
        if env_dict is None:
            env_dict = dict(os.environ.copy())
            kw.update({'env': env_dict})

        # see if KERNEL_LAUNCH_TIMEOUT was included from user
        self.kernel_launch_timeout = float(env_dict.get('KERNEL_LAUNCH_TIMEOUT', elyra_kernel_launch_timeout))

        # add the applicable kernel_id to the env dict
        env_dict['KERNEL_ID'] = self.kernel_id
        for k in env_pop_list:
            env_dict.pop(k, None)
        self.log.debug("BaseProcessProxy.launch_process() env: {}".format(kw.get('env')))

    def cleanup(self):
        pass

    def poll(self):
        # If we have a local process, use its method, else send signal 0 to determine its heartbeat.
        if self.local_proc:
            return self.local_proc.poll()

        return self.send_signal(0)

    def wait(self):
        # If we have a local_proc, call its wait method.  This will cleanup any defunct processes when the kernel
        # is shutdown (when using waitAppCompletion = false).  Otherwise (if no local_proc) we'll use polling to
        # determine if a (remote or revived) process is still active.
        if self.local_proc:
            return self.local_proc.wait()

        for i in range(max_poll_attempts):
            if self.poll():
                time.sleep(poll_interval)
            else:
                break
        else:
            self.log.warning("Wait timeout of {} seconds exhausted. Continuing...".
                             format(max_poll_attempts*poll_interval))

    def send_signal(self, signum):
        # if we have a local process, use its method, else determine if the ip is local or remote and issue
        # the appropriate version to signal the process.
        result = None
        if self.local_proc:
            result = self.local_proc.send_signal(signum)
        else:
            if self.ip and self.pid > 0:
                if self.is_local_ip(self.ip):
                    result = self.local_signal(signum)
                else:
                    result = self.remote_signal(signum)
        return result

    def kill(self):
        # If we have a local process, use its method, else send signal SIGKILL to terminate.
        result = None
        if self.local_proc:
            result = self.local_proc.kill()
            self.log.debug("BaseProcessProxy.kill(): {}".format(result))
        else:
            if self.ip and self.pid > 0:
                if self.is_local_ip(self.ip):
                    result = self.local_signal(signal.SIGKILL)
                else:
                    result = self.remote_signal(signal.SIGKILL)
        return result

    def is_local_ip(self, ip):
        return localinterfaces.is_public_ip(ip) or localinterfaces.is_local_ip(ip)

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

    def rsh(self, host, command):
        ssh = self._getSSHClient(host)
        try:
            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()
        except Exception as e:
            # Let caller decide if exception should be logged
            raise e

        finally:
            if ssh:
                ssh.close()

        return lines

    def rcp(self, host, src_file, dst_file, pull=False):
        """ Copies src_file to dst_file.  If pull is True, the file is pulled (via get),
            else the file is pushed (via put).  If a current ssh connection is not included,
            one will be created and closed.

        :return: True if the remote copy succeeds, otherwise raise Exception.
        """

        # Check if we're performing a loopback copy.  If so, skip it...
        if self.is_local_ip(gethostbyname(host)) and src_file == dst_file:
            # Note: we still need to enforce existence since FileNotFoundError is retried.
            exists = os.path.isfile(dst_file)
            if not exists:
                raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), dst_file)
            return True

        ssh = self._getSSHClient(host)
        try:
            sftp = ssh.open_sftp()
            sftp.get(src_file, dst_file) if pull else sftp.put(src_file, dst_file)
        except Exception as e:
            # Let caller decide if exception should be logged
            raise e
        finally:
            if ssh:
                ssh.close()
        return True

    def remote_signal(self, signum):
        val = None
        # Use a negative signal number to signal process group
        cmd = 'kill -{} {}; echo $?'.format(signum, self.pid)
        if signum > 0:  # only log if meaningful signal (not for poll)
            self.log.debug("Sending signal: -{} to pid: {} on host: {}".format(signum, self.pid, self.ip))
        result = self.rsh(self.ip, cmd)
        for line in result:
            val = line.strip()
        if val == '0':
            return None
        return False

    def local_signal(self, signum):
        # Use a negative signal number to signal process group
        if self.pid > 0:
            cmd = ['kill', '-'+str(signum), str(self.pid)]
            result = subprocess.call(cmd)
            if result == 0:
                return None
        return False

    def get_connection_filename(self):
        """
            Although we're just using the same connection file (location) on the remote system, go ahead and 
            keep this method in case we want the remote connection file to be in a different location.  Should
            we decide to keep the current code, we should probably force the local location by requiring that
            either JUPYTER_DATA_DIR or JUPYTER_RUNTIME_DIR envs be set and issue a warning if not - which could
            also be done from this method.
        """
        return self.kernel_manager.connection_file

    def get_process_info(self):
        process_info = {'pid': self.pid, 'ip': self.ip}
        return process_info

    def load_process_info(self, process_info):
        self.pid = process_info['pid']
        self.ip = process_info['ip']


class LocalProcessProxy(BaseProcessProxyABC):

    def __init__(self, kernel_manager):
        super(LocalProcessProxy, self).__init__(kernel_manager)
        kernel_manager.ip = localinterfaces.LOCALHOST

    def launch_process(self, kernel_cmd, **kw):
        super(LocalProcessProxy, self).launch_process(kernel_cmd, **kw)

        # launch the local run.sh
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip
        return self


class RemoteProcessProxy(with_metaclass(abc.ABCMeta, BaseProcessProxyABC)):

    def __init__(self, kernel_manager):
        super(RemoteProcessProxy, self).__init__(kernel_manager)
        self.response_socket = None
        self.start_time = None
        self.assigned_ip = None
        self.assigned_host = ''
        self.prepare_socket()

    def launch_process(self, kernel_cmd, **kw):
        super(RemoteProcessProxy, self).launch_process(kernel_cmd, **kw)
        self.kernel_manager.cleanup_connection_file()

    @abc.abstractmethod
    def handle_timeout(self):
        pass

    @abc.abstractmethod
    def confirm_remote_startup(self, kernel_cmd, **kw):
        pass

    def prepare_socket(self):
        s = socket(AF_INET, SOCK_STREAM)
        s.bind((local_ip, 0))
        port = s.getsockname()[1]
        self.log.debug("Response socket bound to port: {} using {}s timeout".format(port, socket_timeout))
        s.listen(1)
        s.settimeout(socket_timeout)
        self.kernel_manager.response_address = local_ip + ':' + str(port)
        self.response_socket = s

    def receive_connection_info(self):
        # Polls the socket using accept.  When data is found, returns ready indicator and json data
        ready_to_connect = False
        if self.response_socket:
            conn = None
            data = ''
            try:
                conn, addr = self.response_socket.accept()
                while 1:
                    buffer = conn.recv(1024)
                    if not buffer: # send is complete
                        self.log.debug("Received data for KernelID '{}' on host '{}' on connection {}..."
                                       .format(self.kernel_id, self.assigned_host, addr))
                        connect_info = json.loads(data)
                        ready_to_connect = True
                        self.update_connection(connect_info)
                        break
                    data = data + buffer # append what we received until we get no more...
            except Exception as e:
                if type(e) is timeout:
                    self.log.debug("Waiting for KernelID '{}' to send connection info from host '{}' - retyring..."
                                   .format(self.kernel_id, self.assigned_host))
                else:
                    self.log.error(
                        "Exception '{}' occurred waiting for connection file response for KernelId '{}' "
                        "on host '{}'".format(type(e).__name__, self.kernel_id, self.assigned_host))
                    self.kill()
                    raise e
            finally:
                if conn:
                    conn.close()
        else:
            raise tornado.web.HTTPError(500,
                                        "Unexpected runtime found for KernelID '{}'!  "
                                        "No response socket exists".format(self.kernel_id))
        return ready_to_connect

    def update_connection(self, connect_info=None):
        # Reset the ports to 0 so load can take place (which resets the members to value from file or json)...
        self.kernel_manager.stdin_port = self.kernel_manager.iopub_port = self.kernel_manager.shell_port = \
            self.kernel_manager.hb_port = self.kernel_manager.control_port = 0

        if connect_info:
            connect_info['ip'] = self.assigned_ip  # overwrite the ip to our remote target
            self.kernel_manager.load_connection_info(info=connect_info)

            if self.is_local_ip(self.assigned_ip):
                # if loopback - file is already good to go and loaded.
                self.log.debug("Using existing connection file '{}'.".format(self.kernel_manager.connection_file))
            else:
                self.kernel_manager.cleanup_connection_file()  # remove the original file (retaining members)
                self.kernel_manager.write_connection_file()    # write members to file so its marked as written
                self.log.debug("Successfully updated connection file '{}'.".format(self.kernel_manager.connection_file))
        else:
            # push or pull mode - so we already have the file in place - just load
            self.kernel_manager.load_connection_file(connection_file=self.kernel_manager.connection_file)
            self.kernel_manager.ip = self.assigned_ip # overwrite the ip to our remote target

        self.kernel_manager._connection_file_written = True  # allows for cleanup of local files

    def get_process_info(self):
        process_info = super(RemoteProcessProxy, self).get_process_info()
        process_info.update({'assigned_ip': self.assigned_ip,
                             'assigned_host': self.assigned_host})
        return process_info

    def load_process_info(self, process_info):
        super(RemoteProcessProxy, self).load_process_info(process_info)
        self.assigned_ip = process_info['assigned_ip']
        self.assigned_host = process_info['assigned_host']

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


class DistributedProcessProxy(RemoteProcessProxy):
    host_index = 0

    def __init__(self, kernel_manager):
        super(DistributedProcessProxy, self).__init__(kernel_manager)
        self.hosts = self.get_hosts()

    def get_hosts(self):
        # Called during construction to set self.hosts
        return os.getenv('ELYRA_REMOTE_HOSTS', 'localhost').split(',')

    def launch_process(self, kernel_cmd, **kw):
        super(DistributedProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.assigned_host = self.determine_next_host()
        self.ip = gethostbyname(self.assigned_host)  # convert to ip if host is provided
        self.assigned_ip = self.ip

        cmd = self.build_startup_command(kernel_cmd, **kw)
        self.log.debug("Invoking cmd: '{}' on host: {}".format(cmd, self.assigned_host))
        result_pid = 'bad_pid'  # purposely initialize to bad int value

        result = self.rsh(self.ip, cmd)
        for line in result:
            result_pid = line.strip()

        try:
            self.pid = int(result_pid)
        except ValueError:
            raise RuntimeError("Failure occurred starting remote kernel on '{}'.  Returned result: {}"
                               .format(self.ip, result))

        self.log.info("Remote kernel launched on '{}', pid: {}, KernelID: {}, cmd: '{}'"
                      .format(self.assigned_host, self.pid, self.kernel_id, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

        return self

    def cleanup(self):
        val = None
        cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
        self.log.debug("Removing connection file via: '{}' on host: {}".format(cmd, self.ip))
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
        # Add additional envs not in kernelspec...
        env_dict = kw['env']

        kuser = env_dict.get('KERNEL_USERNAME')
        if kuser:
            cmd += 'export KERNEL_USERNAME="{}";'.format(kuser)
        kid = env_dict.get('KERNEL_ID')
        if kid:
            cmd += 'export KERNEL_ID="{}";'.format(kid)

        for key, value in self.kernel_manager.kernel_spec.env.items():
            cmd += "export {}={};".format(key, json.dumps(value).replace("'","''"))

        cmd += 'nohup'
        for arg in argv_cmd:
            cmd += ' {}'.format(arg)

        cmd += ' >> {} 2>&1 & echo $!'.format(proxy_launch_log)

        return cmd

    def determine_next_host(self):
        next_host = self.hosts[DistributedProcessProxy.host_index % self.hosts.__len__()]
        DistributedProcessProxy.host_index += 1
        return next_host

    def confirm_remote_startup(self, kernel_cmd, **kw):
        """ Confirms the remote application has started by obtaining connection information from the remote
            host based on the connection file mode.
        """
        self.start_time = RemoteProcessProxy.get_current_time()
        i = 0
        ready_to_connect = False  # we're ready to connect when we have a connection file to use
        while not ready_to_connect:
            i += 1
            self.handle_timeout()

            self.log.debug("{}: Waiting to connect.  Host: '{}', KernelID: '{}'".
                           format(i, self.assigned_host, self.kernel_id))

            if self.assigned_host != '':
                ready_to_connect = self.receive_connection_info()

    def handle_timeout(self):
        time.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            error_http_code = 500
            reason = "Waited too long ({}s) to get connection file".format(self.kernel_launch_timeout)
            self.kill()
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log.error(timeout_message)
            raise tornado.web.HTTPError(error_http_code, timeout_message)


class YarnClusterProcessProxy(RemoteProcessProxy):

    yarn_endpoint = os.getenv('ELYRA_YARN_ENDPOINT', 'http://localhost:8088/ws/v1/cluster')
    initial_states = {'NEW', 'SUBMITTED', 'ACCEPTED', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED'}  # Don't include FAILED state

    def __init__(self,  kernel_manager):
        super(YarnClusterProcessProxy, self).__init__(kernel_manager)
        self.application_id = None
        yarn_master = urlparse(YarnClusterProcessProxy.yarn_endpoint).hostname
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
                       .format(YarnClusterProcessProxy.yarn_endpoint, self.local_proc.pid, self.kernel_id, kernel_cmd))
        self.confirm_remote_startup(kernel_cmd, **kw)

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
            state = YarnClusterProcessProxy.query_app_state_by_id(self.application_id)
            if state in YarnClusterProcessProxy.initial_states:
                result = None

        # The following produces too much output (every 3 seconds by default), so commented-out at this time.
        #self.log.debug("YarnProcessProxy.poll, application ID: {}, kernel ID: {}, state: {}".
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
        elif signum == signal.SIGINT:
            self.log.debug("YarnClusterProcessProxy.send_signal, SIGINT requests will be ignored")
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
            resp = YarnClusterProcessProxy.kill_app_by_id(self.application_id)
            self.log.debug("YarnClusterProcessProxy.kill_app_by_id response: {}, confirming app state is not RUNNING".format(resp))

            i, state = 1, YarnClusterProcessProxy.query_app_state_by_id(self.application_id)
            while state not in YarnClusterProcessProxy.final_states and i <= max_poll_attempts:
                time.sleep(poll_interval)
                state = YarnClusterProcessProxy.query_app_state_by_id(self.application_id)
                i = i+1

            if state in YarnClusterProcessProxy.final_states:
                result = None

        super(YarnClusterProcessProxy, self).kill()

        self.log.debug("YarnClusterProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}"
                       .format(self.application_id, self.kernel_id, state))
        return result

    def cleanup(self):
        self.log.debug("YarnClusterProcessProxy.cleanup: Removing connection file from assigned host: {}".
                       format(self.assigned_host))
        cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
        self.rsh(self.assigned_ip, cmd)

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
                self.app_state = self.get_application_state()

                if self.app_state in YarnClusterProcessProxy.final_states:
                    raise tornado.web.HTTPError(500, "KernelID: '{}', ApplicationID: '{}' unexpectedly found in"
                        "state '{}' during kernel startup!".format(self.kernel_id, self.application_id, self.app_state))

                self.log.debug("{}: State: '{}', Host: '{}', KernelID: '{}', ApplicationID: '{}'".
                               format(i, self.app_state, self.assigned_host, self.kernel_id, self.application_id))

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
            reason = "Application ID is None. Failed to submit a new application to YARN within {} seconds.".\
                format(self.kernel_launch_timeout)
            error_http_code = 500
            if self.get_application_id(True):
                if YarnClusterProcessProxy.query_app_state_by_id(self.application_id) != "RUNNING":
                    reason = "YARN resources unavailable after {} seconds for app {}, launch timeout: {}!".\
                        format(time_interval, self.application_id, self.kernel_launch_timeout)
                    error_http_code = 503
                else:
                    reason = "App {} is RUNNING, but waited too long ({} secs) to get connection file".\
                        format(self.application_id, self.kernel_launch_timeout)
            self.kill()
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            self.log.error(timeout_message)
            raise tornado.web.HTTPError(error_http_code, timeout_message)

    def get_application_id(self, ignore_final_states=False):
        # Return the kernel's YARN application ID if available, otherwise None.  If we're obtaining application_id
        # from scratch, do not consider kernels in final states.  TODO - may need to treat FAILED state differently.
        if not self.application_id:
            app = self.query_app_by_name(self.kernel_id)
            state_condition = True
            if app and ignore_final_states:
                state_condition = app.get('state') not in YarnClusterProcessProxy.final_states

            if app and len(app.get('id', '')) > 0 and state_condition:
                self.application_id = app['id']
                time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())
                self.log.info("ApplicationID: '{}' assigned for KernelID: '{}', state: {}, {} seconds after starting."
                              .format(app['id'], self.kernel_id, app.get('state'), time_interval))
            else:
                self.log.info("ApplicationID not yet assigned for KernelID: '{}' - retrying...".format(self.kernel_id))
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
        When submit a new app, it may take a while for YARN to accept and run and generate the application ID.
        Note: if a kernel restarts with the same kernel id as app name, multiple applications will be returned.
        For now, the app/kernel with the top most application ID will be returned as the target app, assuming the app
        ID will be incremented automatically on the YARN side.

        :param kernel_id: as the unique app name for query
        :return: The JSON object of an application. 
        """
        top_most_app_id = ''
        target_app = None
        data = self.resource_mgr.cluster_applications().data
        if data and 'apps' in data and 'app' in data['apps']:
            for app in data['apps']['app']:
                if app.get('name', '').find(kernel_id) >= 0 and app.get('id') > top_most_app_id:
                    target_app = app
                    top_most_app_id = app.get('id')
        return target_app

    def query_yarn_nodes(self):
        """Retrieve all nodes host name in a YARN cluster.
        
        :return: A list of "nodeHostName" from JSON object
        """
        data = self.resource_mgr.cluster_nodes().data
        nodes_list = list([])
        if data and 'nodes' in data and 'node' in data['nodes']:
            for node in data['nodes']['node']:
                nodes_list.append(node['nodeHostName'])
        return nodes_list

    def query_app_by_id(self, app_id):
        """Retrieve an application by application ID.

        :param app_id
        :return: The JSON object of an application.
        """
        data = self.resource_mgr.cluster_application(application_id=app_id).data
        if data and 'app' in data:
            return data['app']
        return None

    @staticmethod
    def query_app_state_by_id(app_id):
        """Return the state of an application.

        :param app_id: 
        :return: 
        """
        url = '%s/apps/%s/state' % (YarnClusterProcessProxy.yarn_endpoint, app_id)
        cmd = ['curl', '-X', 'GET', url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
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
        url = '%s/apps/%s/state' % (YarnClusterProcessProxy.yarn_endpoint, app_id)
        cmd = ['curl', '-X', 'PUT', '-H', header, '-d', data, url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        output, stderr = process.communicate()
        return json.loads(output) if output else None
