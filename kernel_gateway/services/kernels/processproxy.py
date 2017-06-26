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
from jupyter_client import launch_kernel, localinterfaces
from yarn_api_client.resource_manager import ResourceManager
from datetime import datetime

# Default logging level of paramiko produces too much noise - raise to warning only.
logging.getLogger('paramiko').setLevel(os.getenv('ELYRA_SSH_LOG_LEVEL', logging.WARNING))

# TODO - properly deal with environment variables - some should be promoted to properties

# Pop certain env variables that don't need to be logged, e.g. password
env_pop_list = ['ELYRA_REMOTE_PWD', 'LS_COLORS']
username = os.getenv('ELYRA_REMOTE_USER')
password = os.getenv('ELYRA_REMOTE_PWD')  # this should use password-less ssh
proxy_launch_log = os.getenv('ELYRA_PROXY_LAUNCH_LOG', '/var/log/elyra/proxy_launch.log')
elyra_kernel_launch_timeout = float(os.getenv('ELYRA_KERNEL_LAUNCH_TIMEOUT', '30'))
max_poll_attempts = int(os.getenv('ELYRA_MAX_POLL_ATTEMPTS', '5'))
poll_interval = float(os.getenv('ELYRA_POLL_INTERVAL', '1.0'))

# Connection File Mode values...
CF_MODE_PUSH = 'push'
CF_MODE_PULL = 'pull'
CF_MODE_SOCKET = 'socket'
connection_file_modes = {CF_MODE_PUSH, CF_MODE_PULL, CF_MODE_SOCKET}

local_ip = localinterfaces.public_ips()[0]

class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """

    def __init__(self, kernel_manager, connection_file_mode, **kw):
        self.kernel_manager = kernel_manager

        self.connection_file_mode = connection_file_mode
        if self.connection_file_mode:
            if self.connection_file_mode not in connection_file_modes:
                self.log.warning("Unknown connection file mode detected '{}'!  Continuing...".
                                 format(self.connection_file_mode))

        self.log = kernel_manager.log
        # extract the kernel_id string from the connection file and set the KERNEL_ID environment variable
        self.kernel_id = os.path.basename(self.kernel_manager.connection_file). \
            replace('kernel-', '').replace('.json', '')

        # ask the subclass for the set of applicable hosts
        self.hosts = self.get_hosts()

        env_dict = kw['env']
        # see if KERNEL_LAUNCH_TIMEOUT was included from user
        self.kernel_launch_timeout = float(env_dict.get('KERNEL_LAUNCH_TIMEOUT', elyra_kernel_launch_timeout))

        # add the applicable kernel_id to the env dict
        env_dict['KERNEL_ID'] = self.kernel_id
        for k in env_pop_list:
            env_dict.pop(k, None)
        self.log.debug("BaseProcessProxy env: {}".format(kw['env']))

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
        pass

    def cleanup(self):
        pass

    def get_hosts(self):
        pass

    def poll(self):
        # If we have a local process, use its method, else send signal 0 to determine its heartbeat.
        if self.local_proc:
            return self.local_proc.poll()

        return self.send_signal(0)

    def wait(self):
        # Rather than issue a blocking wait call (if we have the local_proc), use poll with max attempts so
        # we don't block forever.
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

    def rsh(self, host, command, src_file=None, dst_file=None):
        ssh = self._getSSHClient(host)
        try:
            if src_file is not None and dst_file is not None:
                self.rcp(host, src_file, dst_file, ssh)

            # Let caller perform logging since this can be used by poll() calls (every 3 seconds)
            #self.log.debug("Executing command '{}' on host '{}' ...".format(command, host))
            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()
        except Exception as e:
            # Let caller decide if exception should be logged
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
        msg_direction = "from" if pull else "on"

        # Check if we're performing a loopback copy.  If so, skip it...
        if self.is_local_ip(gethostbyname(host)) and src_file == dst_file:
            self.log.debug("Copy of file '{}' to '{}' {} host '{}' skipped - loopback detected.".
                            format(src_file, dst_file, msg_direction, host))
            return True

        close_connection = False
        if ssh is None:
            close_connection = True
            ssh = self._getSSHClient(host)

        msg_direction = "from" if pull else "on"
        try:
            self.log.debug("Copying file '{}' to file '{}' {} host '{}' ...".
                           format(src_file, dst_file, msg_direction, host))
            sftp = ssh.open_sftp()
            sftp.get(src_file, dst_file) if pull else sftp.put(src_file, dst_file)
        except Exception as e:
            # Let caller decide if exception should be logged
            raise e
        finally:
            if close_connection and ssh:
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

    def __init__(self, kernel_manager, connection_file_mode, **kw):
        super(LocalProcessProxy, self).__init__(kernel_manager, connection_file_mode, **kw)

    def launch_process(self, kernel_cmd, **kw):
        super(LocalProcessProxy, self).launch_process(kernel_cmd, **kw)

        # launch the local run.sh
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip
        return self


class StandaloneProcessProxy(BaseProcessProxyABC):
    host_index = 0

    def __init__(self, kernel_manager, connection_file_mode, **kw):
        super(StandaloneProcessProxy, self).__init__(kernel_manager, connection_file_mode, **kw)
        if not self.connection_file_mode:
            self.connection_file_mode = CF_MODE_PUSH
        if self.connection_file_mode != CF_MODE_PUSH:
            self.log.warning("StandaloneProcessProxy only supports connection file mode '{}' at this time - "
                             "detected mode '{}'!  Resetting to '{}' or env override..."
                             .format(CF_MODE_PUSH, self.connection_file_mode, CF_MODE_PUSH))
            self.connection_file_mode = os.getenv('ELYRA_CONNECTION_FILE_MODE', CF_MODE_PUSH).lower()

    def get_hosts(self):
        # Called during construction to set self.hosts
        return os.getenv('ELYRA_REMOTE_HOSTS', 'localhost').split(',')

    def launch_process(self, kernel_cmd, **kw):
        super(StandaloneProcessProxy, self).launch_process(kernel_cmd, **kw)

        self.ip = gethostbyname(self.determine_next_host())  # convert to ip if host is provided

        # write out connection file - which has the remote IP - prior to copy...
        self.kernel_manager.ip = self.ip
        self.kernel_manager.cleanup_connection_file()
        self.kernel_manager.write_connection_file()

        cmd = self.build_startup_command(kernel_cmd, **kw)
        self.log.debug("Invoking cmd: '{}' on host: {}".format(cmd, self.ip))
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

    yarn_endpoint = os.getenv('ELYRA_YARN_ENDPOINT', 'http://localhost:8088/ws/v1/cluster')
    resource_mgr = ResourceManager(serviceEndpoint=yarn_endpoint)
    initial_states = {'NEW', 'SUBMITTED', 'ACCEPTED', 'RUNNING'}
    final_states = {'FINISHED', 'KILLED'}  # Don't include FAILED state

    def __init__(self,  kernel_manager, connection_file_mode, **kw):
        super(YarnProcessProxy, self).__init__(kernel_manager, connection_file_mode, **kw)
        self.application_id = None
        self.start_time = None
        self.response_socket = None
        self.assigned_ip = None
        if self.connection_file_mode is None:
            self.connection_file_mode = CF_MODE_PUSH
            if kernel_manager.kernel_spec.language.lower() == 'python':
                self.connection_file_mode = os.getenv('ELYRA_CONNECTION_FILE_MODE', CF_MODE_PULL).lower()

    def get_hosts(self):
        # Called during construction to set self.hosts
        return YarnProcessProxy.query_yarn_nodes()

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

        if self.connection_file_mode == CF_MODE_PUSH:
            self.distribute_connection_files()
        elif self.connection_file_mode == CF_MODE_SOCKET:
            self.prepare_socket(**kw)

        # launch the local run.sh - which is configured for yarn-cluster...
        self.local_proc = launch_kernel(kernel_cmd, **kw)
        self.pid = self.local_proc.pid
        self.ip = local_ip

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

        # The following produces too much output (every 3 seconds by default), so commented-out at this time.
        #self.log.debug("YarnProcessProxy.poll, application ID: {}, kernel ID: {}, state: {}".
        #               format(self.application_id, self.kernel_id, state))
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

        super(YarnProcessProxy, self).kill()

        self.log.debug("YarnProcessProxy.kill, application ID: {}, kernel ID: {}, state: {}"
                       .format(self.application_id, self.kernel_id, state))
        return result

    def cleanup(self):
        if self.connection_file_mode == CF_MODE_PUSH:
            self.log.debug("Removing connection files from host(s): {}".format(self.hosts))
            for host in self.hosts:
                cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
                self.rsh(host, cmd)
        else:  # pull or socket mode
            self.log.debug("Removing connection file from assigned host: {}".format(self.assigned_ip))
            cmd = 'rm -f {}; echo $?'.format(self.get_connection_filename())
            self.rsh(self.assigned_ip, cmd)

        # reset application id to force new query - handles kernel restarts/interrupts
        self.application_id = None
        self.assigned_ip = None

    def distribute_connection_files(self):
        # TODO - look into the parallelizing this - only necessary on push mode
        if self.connection_file_mode == CF_MODE_PUSH:
            self.log.debug("Copying connection file {} to host(s): {}".
                           format(self.kernel_manager.connection_file, self.hosts))

            for host in self.hosts:
                self.rcp(host, self.kernel_manager.connection_file, self.get_connection_filename())

    def prepare_socket(self, **kw):
        s = socket(AF_INET, SOCK_STREAM)
        s.bind((local_ip, 0))
        port = s.getsockname()[1]
        self.log.debug("Response socket bound to port: {}".format(port))
        s.listen(1)
        s.settimeout(1.0)
        kw['env']['KERNEL_RESPONSE_ADDR'] = (local_ip + ':' + str(port))
        self.response_socket = s

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
        ready_to_connect = False  # we're ready to connect when state is RUNNING and we have a connection file to use
        json_info = None  # contains the connection info when socket-mode is used
        while not ready_to_connect:
            time.sleep(poll_interval)
            i += 1
            self.handle_timeout()

            if self.get_application_id(True):
                app_state = YarnProcessProxy.query_app_state_by_id(self.application_id)
                if host == '':
                    app = YarnProcessProxy.query_app_by_id(self.application_id)
                    if app and app.get('amHostHttpAddress'):
                        host = app.get('amHostHttpAddress').split(':')[0]
                        self.log.debug("Kernel '{}' with app ID {} has been assigned to host {}. CurrentState={}, Attempt={}"
                                  .format(self.kernel_id, self.application_id, host, app_state, i))
                        # Set the kernel manager ip to the actual host where the application landed.
                        self.assigned_ip = gethostbyname(host)

                if app_state in YarnProcessProxy.final_states:
                    raise tornado.web.HTTPError(500, "Kernel '{}' with Yarn application ID {} unexpectedly found in"
                        "state '{}' during kernel startup!".format(self.kernel_id, self.application_id, app_state))

                if app_state != 'RUNNING':
                    self.log.debug("Waiting for application to enter 'RUNNING' state. "
                               "KernelID={}, ApplicationID={}, AssignedHost={}, CurrentState={}, Attempt={}".
                               format(self.kernel_id, self.application_id, host, app_state, i))
                else:  # We're in RUNNING state - check on connection file
                    if self.connection_file_mode == CF_MODE_PUSH:  # Using push mode so we have a connection file
                        ready_to_connect = True
                    else:  # pull or socket mode
                        if self.connection_file_mode == CF_MODE_PULL:
                            self.log.debug("Pulling connection file {} on host {} to local, ApplicationID={}, Attempt={}".
                                           format(self.get_connection_filename(), host, self.application_id, i))
                            try:
                                if self.rcp(host=host, src_file=self.get_connection_filename(), dst_file=self.kernel_manager.connection_file, pull=True):
                                    self.log.info("Successfully pulled '{}' from host '{}'".format(self.get_connection_filename(), host))
                                    ready_to_connect = True
                            except Exception as e:
                                if type(e) is IOError and e.errno == 2:
                                    self.log.debug("No such file when pulling {} for {}, need to retry.".format(
                                        self.get_connection_filename(), self.application_id))
                                else:
                                    self.log.error("Exception '{}' occured when pulling connection file from host '{}', app '{}' "
                                            "Kernel ID '{}'".format(type(e).__name__, host, self.application_id, self.kernel_id))
                                    self.kill()
                                    raise e

                        if self.connection_file_mode == CF_MODE_SOCKET:
                            if self.response_socket:
                                conn = None
                                try:
                                    conn, addr = self.response_socket.accept()
                                    while 1:
                                        self.log.debug("Connected to {}...".format(addr))
                                        data = conn.recv(1024)
                                        if not data:
                                            break
                                        json_info = json.loads(data)
                                        ready_to_connect = True
                                except Exception as e:
                                    if type(e) is timeout:
                                        self.log.debug("Waiting for {} to connect back to receive connection info...".
                                            format(self.application_id))
                                    else:
                                        self.log.error(
                                            "Exception '{}' occured when waiting for connection file response for app '{}' "
                                            "Kernel ID '{}'".format(type(e).__name__, self.application_id,
                                                                    self.kernel_id))
                                        self.kill()
                                        raise e
                                finally:
                                    if conn:
                                        conn.close()
                            else:
                                raise tornado.web.HTTPError(500,
                                    "Unexpected runtime found for Kernel '{}' with Yarn application ID {}!  "
                                    "No response socket exists".format(self.kernel_id, self.application_id))
        if ready_to_connect:
            self.update_connection(json_info)

        return

    def update_connection(self, json_info=None):
        # Reset the ports to 0 so load can take place (which resets the members to value from file or json)...
        self.kernel_manager.stdin_port = self.kernel_manager.iopub_port = self.kernel_manager.shell_port = \
            self.kernel_manager.hb_port = self.kernel_manager.control_port = 0

        if json_info:
            self.kernel_manager.load_connection_info(info=json_info)
        else:
            self.kernel_manager.load_connection_file(connection_file=self.kernel_manager.connection_file)

        self.kernel_manager.cleanup_connection_file() # remove the file (retaining members)
        self.kernel_manager.ip = self.assigned_ip # overwrite the ip to our remote target
        self.kernel_manager.write_connection_file()  # write members to file so its marked as written
        self.log.debug("Successfully updated connection file '{}'.".format(self.kernel_manager.connection_file))

    def handle_timeout(self):
        time_interval = YarnProcessProxy.get_time_diff(self.start_time, YarnProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            timeout_message = "Application ID is None. Failed to submit a new application to YARN within {} seconds.".\
                format(self.kernel_launch_timeout)
            error_http_code = 500
            if self.get_application_id(True):
                if YarnProcessProxy.query_app_state_by_id(self.application_id) != "RUNNING":
                    timeout_message = "YARN resources unavailable after {} seconds for app {}, launch timeout: {}!".\
                        format(time_interval, self.application_id, self.kernel_launch_timeout)
                    error_http_code = 503
                elif self.connection_file_mode != CF_MODE_PUSH:
                    timeout_message = "App {} is RUNNING, but waited too long ({} secs) to get connection file".\
                        format(self.application_id, self.kernel_launch_timeout)
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

    def get_process_info(self):
        process_info = super(YarnProcessProxy, self).get_process_info()
        process_info.update({'application_id': self.application_id, 'assigned_ip': self.assigned_ip})
        return process_info

    def load_process_info(self, process_info):
        super(YarnProcessProxy, self).load_process_info(process_info)
        self.application_id = process_info['application_id']
        self.assigned_ip = process_info['assigned_ip']

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
