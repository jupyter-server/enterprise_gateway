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
from tornado import web
import subprocess
from ipython_genutils.py3compat import with_metaclass
from socket import *
from jupyter_client import launch_kernel, localinterfaces, write_connection_file
from calendar import timegm
from notebook import _tz
from ipython_genutils.py3compat import (
     cast_bytes_py2, string_types,
)
from getpass import getpass

# Default logging level of paramiko produces too much noise - raise to warning only.
logging.getLogger('paramiko').setLevel(os.getenv('EG_SSH_LOG_LEVEL', logging.WARNING))

# Pop certain env variables that don't need to be logged, e.g. password
env_pop_list = ['EG_REMOTE_PWD', 'LS_COLORS']
password = os.getenv('EG_REMOTE_PWD')  # this should use password-less ssh
default_kernel_launch_timeout = float(os.getenv('EG_KERNEL_LAUNCH_TIMEOUT', '30'))
max_poll_attempts = int(os.getenv('EG_MAX_POLL_ATTEMPTS', '10'))
poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
socket_timeout = float(os.getenv('EG_SOCKET_TIMEOUT', '5.0'))
secure_ssh = True  # Set to true for testing, promote to env var later

local_ip = localinterfaces.public_ips()[0]
tunnel_ip = localinterfaces.local_ips()[0]


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
        self.username = kernel_manager.parent.parent.remote_user # from command line or env
        self.kernel_launch_timeout = default_kernel_launch_timeout

        # Represents the local process (from popen) if applicable.  Note that we could have local_proc = None even when
        # the subclass is a LocalProcessProxy (or YarnProcessProxy).  This will happen if the JKG is restarted and the
        # persisted kernel-sessions indicate that its now running on a different server.  In those case, we use the ip
        # member variable to determine if the persisted state is local or remote and use signals with the pid to
        # implement the poll, kill and send_signal methods.
        self.local_proc = None
        self.ip = None
        self.pid = 0
        self.pgid = 0

    @abc.abstractmethod
    def launch_process(self, cmd, **kw):
        env_dict = kw.get('env')
        if env_dict is None:
            env_dict = dict(os.environ.copy())
            kw.update({'env': env_dict})

        # see if KERNEL_LAUNCH_TIMEOUT was included from user.  If so, override default
        if env_dict.get('KERNEL_LAUNCH_TIMEOUT'):
            self.kernel_launch_timeout = float(env_dict.get('KERNEL_LAUNCH_TIMEOUT'))

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
            if self.pgid > 0 and hasattr(os, "killpg"):
                try:
                    os.killpg(self.pgid, signum)
                    return result
                except OSError:
                    pass
            result = self.local_proc.send_signal(signum)
        else:
            if self.ip and self.pid > 0:
                if BaseProcessProxyABC.ip_is_local(self.ip):
                    result = self.local_signal(signum)
                else:
                    result = self.remote_signal(signum)
        return result

    def kill(self):
        # If we have a local process, use its method, else signal soft kill first before hard kill.
        result = self.terminate()  # Send -15 signal first
        i = 1
        while self.poll() is None and i <= max_poll_attempts:
            time.sleep(poll_interval)
            i = i + 1
        if i > max_poll_attempts:  # Send -9 signal if process is still alive
            if self.local_proc:
                result = self.local_proc.kill()
                self.log.debug("BaseProcessProxy.kill(): {}".format(result))
            else:
                if self.ip and self.pid > 0:
                    if BaseProcessProxyABC.ip_is_local(self.ip):
                        result = self.local_signal(signal.SIGKILL)
                    else:
                        result = self.remote_signal(signal.SIGKILL)
            self.log.debug("SIGKILL signal sent to pid: {}".format(self.pid))
        return result

    def terminate(self):
        # If we have a local process, use its method, else send signal SIGTERM to soft kill.
        result = None
        if self.local_proc:
            result = self.local_proc.terminate()
            self.log.debug("BaseProcessProxy.terminate(): {}".format(result))
        else:
            if self.ip and self.pid > 0:
                if BaseProcessProxyABC.ip_is_local(self.ip):
                    result = self.local_signal(signal.SIGTERM)
                else:
                    result = self.remote_signal(signal.SIGTERM)
            self.log.debug("SIGTERM signal sent to pid: {}".format(self.pid))
        return result

    @staticmethod
    def ip_is_local(ip):
        return localinterfaces.is_public_ip(ip) or localinterfaces.is_local_ip(ip)

    def _get_ssh_client(self, host):
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
                ssh.connect(host_ip, port=22, username=self.username, password=password)
            else:
                ssh.connect(host_ip, port=22, username=self.username)
        except Exception as e:
            self.log.error("Exception '{}' occurred when creating a SSHClient connecting to '{}' with user '{}', "
                        "message='{}'.".format(type(e).__name__, host, self.username, e))
            if e is paramiko.SSHException or paramiko.AuthenticationException:
                error_message = "Failed to authenticate SSHClient with password" + \
                                " provided" if password else "-less SSH"
                raise tornado.web.HTTPError(403, error_message)
            else:
                raise e
        return ssh

    def rsh(self, host, command):
        ssh = self._get_ssh_client(host)
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

    def remote_signal(self, signum):
        val = None
        # if we have a process group, use that, else use the pid...
        target = '-'+str(self.pgid) if self.pgid > 0 and signum > 0 else str(self.pid)
        cmd = 'kill -{} {}; echo $?'.format(signum, target)
        if signum > 0:  # only log if meaningful signal (not for poll)
            self.log.debug("Sending signal: {} to target: {} on host: {}".format(signum, target, self.ip))
        result = self.rsh(self.ip, cmd)
        for line in result:
            val = line.strip()
        if val == '0':
            return None
        return False

    def local_signal(self, signum):
        # if we have a process group, use that, else use the pid...
        target = '-' + str(self.pgid) if self.pgid > 0 and signum > 0 else str(self.pid)
        if signum > 0:  # only log if meaningful signal (not for poll)
            self.log.debug("Sending signal: {} to target: {}".format(signum, target))
        cmd = ['kill', '-'+str(signum), target]

        with open(os.devnull, 'w') as devnull:
            result = subprocess.call(cmd, stderr=devnull)

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
        process_info = {'pid': self.pid, 'pgid': self.pgid, 'ip': self.ip}
        return process_info

    def load_process_info(self, process_info):
        self.pid = process_info['pid']
        self.pgid = process_info['pgid']
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
        if hasattr(os, "getpgid"):
            try:
                self.pgid = os.getpgid(self.pid)
            except OSError:
                pass
        self.ip = local_ip
        self.log.info("Local kernel launched on '{}', pid: {}, pgid: {}, KernelID: {}, cmd: '{}'"
                      .format(self.ip, self.pid, self.pgid, self.kernel_id, kernel_cmd))
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
        # remove connection file because a) its not necessary any longer since launchers will return
        # the connection information which will (sufficiently) remain in memory and b) launchers
        # landing on this node may want to write to this file and be denied access.
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

    def tunnel_to_kernel(self, connection_info, sshserver, sshkey=None):
        """tunnel connections to a kernel via ssh
        This will open four SSH tunnels from localhost on this machine to the
        ports associated with the kernel.  They can be either direct
        localhost-localhost tunnels, or if an intermediate server is necessary,
        the kernel must be listening on a public IP.
        Parameters
        ----------
        connection_info : dict or str (path)
            Either a connection dict, or the path to a JSON connection file
        sshserver : str
            The ssh sever to use to tunnel to the kernel. Can be a full
            `user@server:port` string. ssh config aliases are respected.
        sshkey : str [optional]
            Path to file containing ssh key to use for authentication.
            Only necessary if your ssh config does not already associate
            a keyfile with the host.
        Returns
        -------
        (shell, iopub, stdin, hb, control) : ints
            The five ports on localhost that have been forwarded to the kernel.
        """
        from zmq.ssh import tunnel
        if isinstance(connection_info, string_types):
            # it's a path, unpack it
            with open(connection_info) as f:
                connection_info = json.loads(f.read())

        cf = connection_info

        lports = tunnel.select_random_ports(5)

        rports = cf['shell_port'], cf['iopub_port'], cf['stdin_port'], cf['hb_port'], cf['control_port']

        port_names = "SHELL", "IOPUB", "STDIN", "HB", "CONTROL"

        remote_ip = cf['ip']

        if tunnel.try_passwordless_ssh(sshserver, sshkey):
            password = False
            self.log.debug("Passwordless SSH test succeeded using OpenSSH client")
        else:
            self.log.debug("Trying to get Password for SSH")
            password = getpass("SSH Password for %s: " % cast_bytes_py2(sshserver))

        for lp, rp, pn in zip(lports, rports, port_names):
            self.log.debug("Starting SSH tunnel; '{}' mapping is 127.0.0.1:'{}' to '{}':'{}'"
                           .format(pn, lp, remote_ip, rp))
            try:
                tunnel.ssh_tunnel(lp, rp, sshserver, remote_ip, sshkey, timeout=300)
            except:
                self.log.error("Could not open OpenSSH tunnel. Exiting.", exc_info=True)
                exit(1)

        return tuple(lports)

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
                    if not buffer:  # send is complete
                        connect_info = json.loads(data)
                        self.log.debug("Connect Info received from the launcher is as follows '{}'".format(connect_info))
                        self.log.debug("Host assgined to the Kernel is: '{}' '{}'".format(self.assigned_host, self.assigned_ip))

                        # Set connection info to IP address of system where the kernel was launched
                        connect_info['ip'] = self.assigned_ip

                        if secure_ssh:
                            ### TODO: This needs to be fleshed out.
                            key_path = '/home/elyra/.ssh/id_rsa'

                            # SSH server will be located on the same machine as where the kernel will start
                            sshserver = self.assigned_ip

                            # Open some tunnels
                            try:
                                # tunnel_ports = self.tunnel_to_kernel(connect_info, sshserver, key_path)
                                tunnel_ports = self.tunnel_to_kernel(connect_info, sshserver)
                                self.log.debug("SSH tunnel local ports: '{}'".format(tunnel_ports))
                            except:
                                # even catch KeyboardInterrupt
                                self.log.error("Could not setup tunnels", exc_info=True)
                                exit(1)

                            # Replace the remote connection ports with the local ports that were used to create SSH tunnels.
                            connect_info['ip'] = tunnel_ip
                            connect_info['shell_port'] = tunnel_ports[0]
                            connect_info['iopub_port'] = tunnel_ports[1]
                            connect_info['stdin_port'] = tunnel_ports[2]
                            connect_info['hb_port'] = tunnel_ports[3]
                            connect_info['control_port'] = tunnel_ports[4]

                        ready_to_connect = True
                        self.update_connection(connect_info)
                        break
                    data = data + buffer  # append what we received until we get no more...
            except Exception as e:
                if type(e) is timeout:
                    self.log.debug("Waiting for KernelID '{}' to send connection info from host '{}' - retrying..."
                                   .format(self.kernel_id, self.assigned_host))
                else:
                    self.log.error(
                        "The following exception occurred waiting for connection file response for KernelId '{}' "
                        "on host '{}': {}".format(self.kernel_id, self.assigned_host, str(e)))
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

    # Do NOT update connect_info with IP and other such artifacts in this method/function.
    def update_connection(self, connect_info):
        # Reset the ports to 0 so load can take place (which resets the members to value from file or json)...
        self.kernel_manager.stdin_port = self.kernel_manager.iopub_port = self.kernel_manager.shell_port = \
            self.kernel_manager.hb_port = self.kernel_manager.control_port = 0

        if connect_info:
            # Load new connection information into memory. No need to write back out to a file or track loopback, etc.
            # The launcher may also be sending back process info, so check and extract
            self.extract_process_info(connect_info)
            self.kernel_manager.load_connection_info(info=connect_info)
            self.log.debug("Received connection info for KernelID '{}' from host '{}': {}..."
                           .format(self.kernel_id, self.assigned_host, connect_info))
        else:
            raise RuntimeError("RemoteProcessProxy.update_connection: connection information is null!")

        self.kernel_manager._connection_file_written = True  # allows for cleanup of local files (as necessary)

    def extract_process_info(self, connect_info):
        pid = connect_info.get('pid')
        if pid:
            self.pid = int(pid)
            self.log.debug("Updated pid to: {}".format(self.pid))
        pgid = connect_info.get('pgid')
        if pgid:
            self.pgid = int(pgid)
            self.log.debug("Updated pgid to: {}".format(self.pgid))
        if pid or pgid:  # if either process ids were updated, update the ip as well and don't use local_proc
            self.ip = self.assigned_ip
            self.local_proc = None

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
        # Return the current time stamp in UTC time epoch format in milliseconds, e.g.
        return timegm(_tz.utcnow().utctimetuple()) * 1000

    @staticmethod
    def get_time_diff(time1, time2):
        # Return the difference between two timestamps in seconds, assuming the timestamp is in milliseconds
        # e.g. the difference between 1504028203000 and 1504028208300 is 5300 milliseconds or 5.3 seconds
        diff = abs(time2 - time1)
        return float("%d.%d" % (diff / 1000, diff % 1000))
