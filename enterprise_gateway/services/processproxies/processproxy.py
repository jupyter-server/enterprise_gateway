# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import os
import sys
import re
import signal
import abc
import json
import paramiko
import logging
import time
import pexpect
import getpass
from tornado import web
import subprocess
import base64
import random
from ipython_genutils.py3compat import with_metaclass
from socket import *
from jupyter_client import launch_kernel, localinterfaces
from calendar import timegm
from notebook import _tz
from zmq.ssh import tunnel
from enum import Enum
from Crypto.Cipher import AES

# Default logging level of paramiko produces too much noise - raise to warning only.
logging.getLogger('paramiko').setLevel(os.getenv('EG_SSH_LOG_LEVEL', logging.WARNING))

# Pop certain env variables that don't need to be logged, e.g. remote_pwd
env_pop_list = ['EG_REMOTE_PWD', 'LS_COLORS']

default_kernel_launch_timeout = float(os.getenv('EG_KERNEL_LAUNCH_TIMEOUT', '30'))
max_poll_attempts = int(os.getenv('EG_MAX_POLL_ATTEMPTS', '10'))
poll_interval = float(os.getenv('EG_POLL_INTERVAL', '0.5'))
socket_timeout = float(os.getenv('EG_SOCKET_TIMEOUT', '5.0'))
tunneling_enabled = bool(os.getenv('EG_ENABLE_TUNNELING', 'False').lower() == 'true')
ssh_port = int(os.getenv('EG_SSH_PORT', '22'))

# Minimum port range size and max retries
min_port_range_size = int(os.getenv('EG_MIN_PORT_RANGE_SIZE', '1000'))
max_port_range_retries = int(os.getenv('EG_MAX_PORT_RANGE_RETRIES', '5'))

# Number of seconds in 100 years as the max keep-alive interval value.
max_keep_alive_interval = 100 * 365 * 24 * 60 * 60

# These envs are not documented and should default to current user and None, respectively.  These
# exist just in case we find them necessary in some configurations (where the service user
# must be different).  However, tests show that that configuration doesn't work - so there
# might be more to do.  At any rate, we'll use these variables for now.
remote_user = os.getenv('EG_REMOTE_USER', getpass.getuser())
remote_pwd = os.getenv('EG_REMOTE_PWD')  # this should use password-less ssh


# Allow users to specify local ips (regular expressions can be used) that should not be included
# when determining the response address.  For example, on systems with many network interfaces,
# some may have their IPs appear the local interfaces list (e.g., docker's 172.17.0.* is an example)
# that should not be used.  This env can be used to indicate such IPs.
local_ip_blacklist = os.getenv('EG_LOCAL_IP_BLACKLIST','').split(',')


def get_local_ip():
    """
    Honor the blacklist-ed IPs, locating the first not in the list.
    """
    for ip in localinterfaces.public_ips():
        is_blacklisted = False
        for blacklisted_ip in local_ip_blacklist:  # exhaust blacklist, applying regexs
            if re.match(blacklisted_ip, ip):
                is_blacklisted = True
                break
        if not is_blacklisted:
            return ip
    return localinterfaces.public_ips()[0]  # all were blacklisted, so go with the first

local_ip = get_local_ip()

random.seed()


class KernelChannel(Enum):
    SHELL = "SHELL"
    IOPUB = "IOPUB"
    STDIN = "STDIN"
    HEARTBEAT = "HB"
    CONTROL = "CONTROL"
    COMMUNICATION = "EG_COMM"  # Optional channel for remote launcher to issue interrupts - NOT a ZMQ channel


class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """

    def __init__(self, kernel_manager, proxy_config):
        self.kernel_manager = kernel_manager
        # Initialize to 0 IP primarily so restarts of remote kernels don't encounter local-only enforcement during
        # relaunch (see jupyter_client.manager.start_kernel().
        self.kernel_manager.ip = '0.0.0.0'
        self.log = kernel_manager.log
        # extract the kernel_id string from the connection file and set the KERNEL_ID environment variable
        self.kernel_id = os.path.basename(self.kernel_manager.connection_file). \
            replace('kernel-', '').replace('.json', '')
        self.kernel_launch_timeout = default_kernel_launch_timeout
        self.lower_port = 0
        self.upper_port = 0
        self._validate_port_range(proxy_config)

        # Handle authorization sets...
        # Take union of unauthorized users...
        self.unauthorized_users = self.kernel_manager.parent.parent.unauthorized_users
        if proxy_config.get('unauthorized_users'):
            self.unauthorized_users = self.unauthorized_users.union(proxy_config.get('unauthorized_users').split(','))

        # Let authorized users override global value - if set on kernelspec...
        if proxy_config.get('authorized_users'):
            self.authorized_users = set(proxy_config.get('authorized_users').split(','))
        else:
            self.authorized_users = self.kernel_manager.parent.parent.authorized_users

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

        self._enforce_authorization(**kw)
        self._enforce_limits(**kw)

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
                             format(max_poll_attempts * poll_interval))

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
            ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
            host_ip = gethostbyname(host)
            if remote_pwd:
                ssh.connect(host_ip, port=ssh_port, username=remote_user, password=remote_pwd)
            else:
                ssh.connect(host_ip, port=ssh_port, username=remote_user)
        except Exception as e:
            http_status_code = 500
            current_host = gethostbyname(gethostname())
            error_message = "Exception '{}' occurred when creating a SSHClient at {} connecting " \
                            "to '{}:{}' with user '{}', message='{}'.".\
                format(type(e).__name__, current_host, host, ssh_port, remote_user, e)
            if e is paramiko.SSHException or paramiko.AuthenticationException:
                http_status_code = 403
                error_message_prefix = "Failed to authenticate SSHClient with password"
                error_message = error_message_prefix + (" provided" if remote_pwd else "-less SSH")

            self.log_and_raise(http_status_code=http_status_code, reason=error_message)
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
        target = '-' + str(self.pgid) if self.pgid > 0 and signum > 0 else str(self.pid)
        cmd = 'kill -{} {}; echo $?'.format(signum, target)
        if signum > 0:  # only log if meaningful signal (not for poll)
            self.log.debug("Sending signal: {} to target: {} on host: {}".format(signum, target, self.ip))

        try:
            result = self.rsh(self.ip, cmd)
        except Exception as e:
            self.log.warning("Remote signal({}) to '{}' on host '{}' failed with exception '{}'.".
                             format(signum, target, self.ip, e))
            return False

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

        cmd = ['kill', '-' + str(signum), target]

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

    def _enforce_authorization(self, **kw):
        """
            Regardless of impersonation enablement, this method first adds the appropriate value for 
            EG_IMPERSONATION_ENABLED into environment (for use by kernelspecs), then ensures that KERNEL_USERNAME
            has a value and is present in the environment (again, for use by kernelspecs).  If unset, KERNEL_USERNAME
            will be defaulted to the current user.
            
            Authorization is performed by comparing the value of KERNEL_USERNAME with each value in the set of 
            unauthorized users.  If any (case-sensitive) matches are found, HTTP error 403 (Forbidden) will be raised 
            - preventing the launch of the kernel.  If the authorized_users set is non-empty, it is then checked to
            ensure the value of KERNEL_USERNAME is present in that list.  If not found, HTTP error 403 will be raised.
            
            It is assumed that the kernelspec logic will take the appropriate steps to impersonate the user identified 
            by KERNEL_USERNAME when impersonation_enabled is True.
        """
        # Get the env
        env_dict = kw.get('env')

        # Although it may already be set in the env, just override in case it was only set via command line or config
        # Convert to string since execve() (called by Popen in base classes) wants string values.
        env_dict['EG_IMPERSONATION_ENABLED'] = str(self.kernel_manager.parent.parent.impersonation_enabled)

        # Ensure KERNEL_USERNAME is set
        kernel_username = env_dict.get('KERNEL_USERNAME')
        if kernel_username is None:
            kernel_username = getpass.getuser()
            env_dict['KERNEL_USERNAME'] = kernel_username

        # Now perform authorization checks
        if kernel_username in self.unauthorized_users:
            self._raise_authorization_error(kernel_username, "not authorized")

        # If authorized users are non-empty, ensure user is in that set.
        if self.authorized_users.__len__() > 0:
            if kernel_username not in self.authorized_users:
                self._raise_authorization_error(kernel_username, "not in the set of users authorized")

    def _raise_authorization_error(self, kernel_username, differentiator_clause):
        kernel_name = self.kernel_manager.kernel_spec.display_name
        kernel_clause = " '{}'.".format(kernel_name) if kernel_name is not None else "s."
        error_message = "User '{}' is {} to start kernel{} " \
                        "Ensure KERNEL_USERNAME is set to an appropriate value and retry the request.". \
            format(kernel_username, differentiator_clause, kernel_clause)
        self.log_and_raise(http_status_code=403, reason=error_message)

    def _enforce_limits(self, **kw):
        """
            Enforces any limits that may be imposed by the configuration.
        """

        # if kernels-per-user is configured, ensure that this next kernel is still within the limit.  If this
        # is due to a restart, skip enforcement since we're re-using that id.
        max_kernels_per_user = self.kernel_manager.parent.parent.max_kernels_per_user
        if max_kernels_per_user >= 0 and not self.kernel_manager.restarting:
            env_dict = kw.get('env')
            username = env_dict['KERNEL_USERNAME']
            current_kernel_count = self.kernel_manager.parent.parent.kernel_session_manager.active_sessions(username)
            if current_kernel_count >= max_kernels_per_user:
                error_message = "A max kernels per user limit has been set to {} and user '{}' currently has {} " \
                                "active {}.".format(max_kernels_per_user, username, current_kernel_count,
                                                    "kernel" if max_kernels_per_user == 1 else "kernels")
                self.log_and_raise(http_status_code=403, reason=error_message)

    def get_process_info(self):
        process_info = {'pid': self.pid, 'pgid': self.pgid, 'ip': self.ip}
        return process_info

    def load_process_info(self, process_info):
        self.pid = process_info['pid']
        self.pgid = process_info['pgid']
        self.ip = process_info['ip']
        self.kernel_manager.ip = process_info['ip']

    def _validate_port_range(self, proxy_config):
        # Let port_range override global value - if set on kernelspec...
        port_range = self.kernel_manager.parent.parent.port_range
        if proxy_config.get('port_range'):
            port_range = proxy_config.get('port_range')

        try:
            port_ranges = port_range.split("..")

            self.lower_port = int(port_ranges[0])
            self.upper_port = int(port_ranges[1])

            port_range_size = self.upper_port - self.lower_port
            if port_range_size != 0:
                if port_range_size < min_port_range_size:
                    self.log_and_raise(http_status_code=500, reason="Port range validation failed for range: '{}'.  "
                        "Range size must be at least {} as specified by env EG_MIN_PORT_RANGE_SIZE".
                        format(port_range, min_port_range_size))

                # According to RFC 793, port is a 16-bit unsigned int. Which means the port
                # numbers must be in the range (0, 65535). However, within that range,
                # ports 0 - 1023 are called "well-known ports" and are typically reserved for
                # specific purposes. For example, 0 is reserved for random port assignment,
                # 80 is used for HTTP, 443 for TLS/SSL, 25 for SMTP, etc. But, there is
                # flexibility as one can choose any port with the aforementioned protocols.
                # Ports 1024 - 49151 are called "user or registered ports" that are bound to
                # services running on the server listening to client connections. And, ports
                # 49152 - 65535 are called "dynamic or ephemeral ports". A TCP connection
                # has two endpoints. Each endpoint consists of an IP address and a port number.
                # And, each connection is made up of a 4-tuple consisting of -- client-IP,
                # client-port, server-IP, and server-port. A service runs on a server with a
                # specific IP and is bound to a specific "user or registered port" that is
                # advertised for clients to connect. So, when a client connects to a service
                # running on a server, three out of 4-tuple - client-IP, client-port, server-IP -
                # are already known. To be able to serve multiple clients concurrently, the
                # server's IP stack assigns an ephemeral port for the connection to complete
                # the 4-tuple.
                #
                # In case of JEG, we will accept ports in the range 1024 - 65535 as these days
                # admins use dedicated hosts for individual services.
                if self.lower_port < 1024 or self.lower_port > 65535:
                    self.log_and_raise(http_status_code=500, reason="Invalid port range '{}' specified. "
                                    "Range for valid port numbers is (1024, 65535).".format(port_range))
                if self.upper_port < 1024 or self.upper_port > 65535:
                    self.log_and_raise(http_status_code=500, reason="Invalid port range '{}' specified. "
                                    "Range for valid port numbers is (1024, 65535).".format(port_range))
        except ValueError as ve:
            self.log_and_raise(http_status_code=500, reason="Port range validation failed for range: '{}'.  "
                            "Error was: {}".format(port_range, ve))
        except IndexError as ie:
            self.log_and_raise(http_status_code=500, reason="Port range validation failed for range: '{}'.  "
                            "Error was: {}".format(port_range, ie))

        self.kernel_manager.port_range = port_range

    def select_ports(self, count):
        """Select and return n random ports that are available and adhere to the given port range, if applicable."""
        ports = []
        sockets = []
        for i in range(count):
            sock = self.select_socket()
            ports.append(sock.getsockname()[1])
            sockets.append(sock)
        for sock in sockets:
            sock.close()
        return ports

    def select_socket(self, ip=''):
        """Create and return a socket whose port is available and adheres to the given port range, if applicable."""
        sock = socket(AF_INET, SOCK_STREAM)
        found_port = False
        retries = 0
        while not found_port:
            try:
                sock.bind((ip, self._get_candidate_port()))
                found_port = True
            except Exception as e:
                retries = retries + 1
                if retries > max_port_range_retries:
                    self.log_and_raise(http_status_code=500, reason="Failed to locate port within range {} "
                            "after {} retries!".format(self.kernel_manager.port_range, max_port_range_retries))
        return sock

    def _get_candidate_port(self):
        range_size = self.upper_port - self.lower_port
        if range_size == 0:
            return 0
        return random.randint(self.lower_port, self.upper_port)

    def log_and_raise(self, http_status_code=None, reason=None):
        """
        Helper method that combines the logging and raising of exceptions.  If http_status_code is
        is provided an HTTPError is created using the status code and reason.  If http_status_code is
        not provided, a RuntimeError is raised with reason as the message.  In either case, an error is
        logged using the reason.  If reason is not provided a generic message will be used.
        :param http_status_code:
        :param reason:
        :return:
        """
        if reason is None:
            reason = "Internal server issue!"

        self.log.error(reason)
        if http_status_code:
            raise web.HTTPError(status_code=http_status_code, reason=reason)
        else:
            raise RuntimeError(reason)


class LocalProcessProxy(BaseProcessProxyABC):
    def __init__(self, kernel_manager, proxy_config):
        super(LocalProcessProxy, self).__init__(kernel_manager, proxy_config)
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
    def __init__(self, kernel_manager, proxy_config):
        super(RemoteProcessProxy, self).__init__(kernel_manager, proxy_config)
        self.response_socket = None
        self.start_time = None
        self.assigned_ip = None
        self.assigned_host = ''
        self.comm_ip = None
        self.comm_port = 0
        self.tunneled_connect_info = None    # Contains the destination connection info when tunneling in use
        self.tunnel_processes = {}
        self._prepare_response_socket()

    def launch_process(self, kernel_cmd, **kw):
        # Pass along port-range info to kernels...
        kw['env']['EG_MIN_PORT_RANGE_SIZE'] = str(min_port_range_size)
        kw['env']['EG_MAX_PORT_RANGE_RETRIES'] = str(max_port_range_retries)

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

    def _prepare_response_socket(self):
        s = self.select_socket(local_ip)
        port = s.getsockname()[1]
        self.log.debug("Response socket launched on {}, port: {} using {}s timeout".format(local_ip, port, socket_timeout))
        s.listen(1)
        s.settimeout(socket_timeout)
        self.kernel_manager.response_address = local_ip + ':' + str(port)
        self.response_socket = s

    def _tunnel_to_kernel(self, connection_info, server, port=ssh_port, key=None):
        """Tunnel connections to a kernel over SSH
        This will open five SSH tunnels from localhost on this machine to the
        ports associated with the kernel.
        See jupyter_client/connect.py for original implementation.
        """
        cf = connection_info

        lports = self.select_ports(5)

        rports = cf['shell_port'], cf['iopub_port'], cf['stdin_port'], cf['hb_port'], cf['control_port']

        channels = KernelChannel.SHELL, KernelChannel.IOPUB, KernelChannel.STDIN, \
            KernelChannel.HEARTBEAT, KernelChannel.CONTROL

        remote_ip = cf['ip']

        if not tunnel.try_passwordless_ssh(server + ":" + str(port), key):
            self.log_and_raise(http_status_code=403, reason="Must use password-less scheme by setting up the "
                            "SSH public key on the cluster nodes")

        for lp, rp, kc in zip(lports, rports, channels):
            self._create_ssh_tunnel(kc, lp, rp, remote_ip, server, port, key)

        return tuple(lports)

    def _tunnel_to_port(self, kernel_channel, remote_ip, remote_port, server, port=ssh_port, key=None):
        """Analogous to _tunnel_to_kernel, but deals with a single port.  This will typically called for
        any one-off ports that require tunnelling. Note - this method assumes that passwordless ssh is
        in use and has been previously validated.
        """
        local_port = self.select_ports(1)[0]
        self._create_ssh_tunnel(kernel_channel, local_port, remote_port, remote_ip, server, port, key)
        return local_port

    def _create_ssh_tunnel(self, kernel_channel, local_port, remote_port, remote_ip, server, port, key):
        channel_name = kernel_channel.value
        self.log.debug("Creating SSH tunnel for '{}': 127.0.0.1:'{}' to '{}':'{}'"
                       .format(channel_name, local_port, remote_ip, remote_port))
        try:
            process = self._spawn_ssh_tunnel(kernel_channel, local_port, remote_port, remote_ip, server, port, key)
            self.tunnel_processes[channel_name] = process
        except Exception as e:
            self.log_and_raise(http_status_code=500, reason="Could not open SSH tunnel for port {}. Exception: '{}'"
                        .format(channel_name, e))

    def _spawn_ssh_tunnel(self, kernel_channel, local_port, remote_port, remote_ip, server, port=ssh_port, key=None):
        """ This method spawns a child process to create a SSH tunnel and returns the spawned process.
            ZMQ's implementation returns a pid on UNIX based platforms and a process handle/reference on
            Win32. By consistently returning a process handle/reference on both UNIX and Win32 platforms,
            this method enables the caller to deal with the same currency regardless of the platform. For
            example, on both UNIX and Win32 platforms, the developer will have the option to stash the
            child process reference and manage it's lifecycle consistently.

            On UNIX based platforms, ZMQ's implementation is more generic to be able to handle various
            use-cases. ZMQ's implementation also requests the spawned process to go to background using
            '-f' command-line option. As a result, the spawned process becomes an orphan and any references
            to the process obtained using it's pid become stale. On the other hand, this implementation is
            specifically for password-less SSH login WITHOUT the '-f' command-line option thereby allowing
            the spawned process to be owned by the parent process. This allows the parent process to control
            the lifecycle of it's child processes and do appropriate cleanup during termination.
        """
        if sys.platform == 'win32':
            ssh_server = server + ":" + str(port)
            return tunnel.paramiko_tunnel(local_port, remote_port, ssh_server, remote_ip, key)
        else:
            ssh = "ssh -p %s -o ServerAliveInterval=%i" % \
                  (port, self._get_keep_alive_interval(kernel_channel))
            cmd = "%s -S none -L 127.0.0.1:%i:%s:%i %s" % (
                ssh, local_port, remote_ip, remote_port, server)
            return pexpect.spawn(cmd, env=os.environ.copy().pop('SSH_ASKPASS', None))

    def _get_keep_alive_interval(self, kernel_channel):
        cull_idle_timeout = self.kernel_manager.parent.cull_idle_timeout

        if (kernel_channel == KernelChannel.COMMUNICATION or
                kernel_channel == KernelChannel.CONTROL or
                cull_idle_timeout <= 0 or
                cull_idle_timeout > max_keep_alive_interval):
            # For COMMUNICATION and CONTROL channels, keep-alive interval will be set to
            # max_keep_alive_interval to make sure that the SSH session does not timeout
            # or expire for a very long time. Also, if cull_idle_timeout is unspecified,
            # negative, or a very large value, then max_keep_alive_interval will be
            # used as keep-alive value.
            return max_keep_alive_interval

        # Ideally, keep-alive interval should be greater than cull_idle_timeout. So, we
        # will add 60seconds to cull_idle_timeout to come up with the value for keep-alive
        # interval for the rest of the kernel channels.
        return cull_idle_timeout + 60

    def _decrypt(self, data):
        decryptAES = lambda c, e: c.decrypt(base64.b64decode(e))
        key = self.kernel_id[0:16]
        # self.log.debug("AES Decryption Key '{}'".format(key))
        cipher = AES.new(key)
        payload = decryptAES(cipher, data)
        payload = "".join([payload.decode("utf-8").rsplit("}", 1)[0], "}"])  # Get rid of padding after the '}'.
        return payload

    def receive_connection_info(self):
        # Polls the socket using accept.  When data is found, returns ready indicator and encrypted data.
        ready_to_connect = False
        if self.response_socket:
            conn = None
            data = ''
            try:
                conn, address = self.response_socket.accept()
                while 1:
                    buffer = conn.recv(1024)
                    if not buffer:  # send is complete, process payload
                        self.log.debug("Received Payload '{}'".format(data))
                        payload = self._decrypt(data)
                        self.log.debug("Decrypted Payload '{}'".format(payload))
                        connect_info = json.loads(payload)
                        self.log.debug("Connect Info received from the launcher is as follows '{}'".
                                       format(connect_info))
                        self.log.debug("Host assigned to the Kernel is: '{}' '{}'".
                                       format(self.assigned_host, self.assigned_ip))

                        self._setup_connection_info(connect_info)
                        ready_to_connect = True
                        break
                    data = data + buffer.decode(encoding='utf-8')  # append what we received until we get no more...
            except Exception as e:
                if type(e) is timeout:
                    self.log.debug("Waiting for KernelID '{}' to send connection info from host '{}' - retrying..."
                                   .format(self.kernel_id, self.assigned_host))
                else:
                    error_message = "Exception occurred waiting for connection file response for KernelId '{}' "\
                        "on host '{}': {}".format(self.kernel_id, self.assigned_host, str(e))
                    self.kill()
                    self.log_and_raise(http_status_code=500, reason=error_message)
            finally:
                if conn:
                    conn.close()
        else:
            error_message = "Unexpected runtime encountered for Kernel ID '{}' - no response socket exists!".\
                format(self.kernel_id)
            self.log_and_raise(http_status_code=500, reason=error_message)

        return ready_to_connect

    def _setup_connection_info(self, connect_info):
        """
        Take connection info (returned from launcher or loaded from session persistence) and properly
        configure port variables for the 5 kernel and (possibly) the launcher communication port.  If
        tunneling is enabled, these ports will be tunneled with the original port information recorded.
        """

        connect_info['ip'] = self.assigned_ip  # Set connection to IP address of system where the kernel was launched

        if tunneling_enabled is True:
            # Capture the current(tunneled) connect_info relative to the IP and ports (including the
            # communication port - if present).
            self.tunneled_connect_info = dict(connect_info)

            # Open tunnels to the 5 ZMQ kernel ports
            tunnel_ports = self._tunnel_to_kernel(connect_info, self.assigned_ip)
            self.log.debug("Local ports used to create SSH tunnels: '{}'".format(tunnel_ports))

            # Replace the remote connection ports with the local ports used to create SSH tunnels.
            connect_info['ip'] = '127.0.0.1'
            connect_info['shell_port'] = tunnel_ports[0]
            connect_info['iopub_port'] = tunnel_ports[1]
            connect_info['stdin_port'] = tunnel_ports[2]
            connect_info['hb_port'] = tunnel_ports[3]
            connect_info['control_port'] = tunnel_ports[4]

            # If a communication port was provided, tunnel it
            if 'comm_port' in connect_info:
                self.comm_ip = connect_info['ip']
                tunneled_comm_port = int(connect_info['comm_port'])
                self.comm_port = self._tunnel_to_port(KernelChannel.COMMUNICATION, self.assigned_ip,
                                                      tunneled_comm_port, self.assigned_ip)
                connect_info['comm_port'] = self.comm_port
                self.log.debug("Established gateway communication to: {}:{} for KernelID '{}' via tunneled port "
                               "127.0.0.1:{}".format(self.assigned_ip, tunneled_comm_port,
                                                     self.kernel_id, self.comm_port))

        else:  # tunneling not enabled, still check for and record communication port
            if 'comm_port' in connect_info:
                self.comm_ip = connect_info['ip']
                self.comm_port = int(connect_info['comm_port'])
                self.log.debug("Established gateway communication to: {}:{} for KernelID '{}'".
                               format(self.assigned_ip, self.comm_port, self.kernel_id))

        # If no communication port was provided, record that fact as well since this is useful to know
        if 'comm_port' not in connect_info:
            self.log.debug("Gateway communication port has NOT been established for KernelID '{}' (optional).".
                           format(self.kernel_id))

        self._update_connection(connect_info)

    def _update_connection(self, connect_info):
        """
        Updates the connection info member variables of the kernel manager.  Also pulls the PID and PGID
        info, if present, in case we need to use it for lifecycle management.
        Note: Do NOT update connect_info with IP and other such artifacts in this method/function.
        """
        # Reset the ports to 0 so load can take place (which resets the members to value from file or json)...
        self.kernel_manager.stdin_port = self.kernel_manager.iopub_port = self.kernel_manager.shell_port = \
            self.kernel_manager.hb_port = self.kernel_manager.control_port = 0

        if connect_info:
            # Load new connection information into memory. No need to write back out to a file or track loopback, etc.
            # The launcher may also be sending back process info, so check and extract
            self._extract_pid_info(connect_info)
            self.kernel_manager.load_connection_info(info=connect_info)
            self.log.debug("Received connection info for KernelID '{}' from host '{}': {}..."
                           .format(self.kernel_id, self.assigned_host, connect_info))
        else:
            error_message = "Unexpected runtime encountered for Kernel ID '{}' - " \
                            "connection information is null!".format(self.kernel_id)
            self.log_and_raise(http_status_code=500, reason=error_message)

        # If there's a response-socket, close it since its no longer needed.
        if self.response_socket:
            self.response_socket.shutdown(SHUT_RDWR)
            self.response_socket.close()
            self.response_socket = None

        self.kernel_manager._connection_file_written = True  # allows for cleanup of local files (as necessary)

    def _extract_pid_info(self, connect_info):
        pid = connect_info.pop('pid', None)
        if pid:
            try:
                self.pid = int(pid)
                self.log.debug("Updated pid to: {}".format(self.pid))
            except ValueError:
                self.log.warning("pid returned from kernel launcher is not an integer: {} - ignoring.".format(pid))
                pid = None
        pgid = connect_info.pop('pgid', None)
        if pgid:
            try:
                self.pgid = int(pgid)
                self.log.debug("Updated pgid to: {}".format(self.pgid))
            except ValueError:
                self.log.warning("pgid returned from kernel launcher is not an integer: {} - ignoring.".format(pgid))
                pgid = None
        if pid or pgid:  # if either process ids were updated, update the ip as well and don't use local_proc
            self.ip = self.assigned_ip
            self.local_proc = None

    def cleanup(self):
        self.assigned_ip = None

        for kernel_channel, process in self.tunnel_processes.items():
            self.log.debug("cleanup: terminating {} tunnel process.".format(kernel_channel))
            process.terminate()

        self.tunnel_processes.clear()
        super(RemoteProcessProxy, self).cleanup()

    def send_signal(self, signum):
        # If the launcher returned a comm_port value, then use that to send the signal,
        # else, defer to the superclass - which will use a remote shell to issue kill.
        # Note that if the target process is running as a different user than the REMOTE_USER,
        # using anything other than the socket-based signal (via signal_addr) will not work.

        if self.comm_port > 0:
            signal_request = dict()
            signal_request['signum'] = signum

            sock = socket(AF_INET, SOCK_STREAM)
            try:
                sock.connect((self.comm_ip, self.comm_port))
                sock.send(json.dumps(signal_request).encode(encoding='utf-8'))
                if signum > 0:  # Polling (signum == 0) is too frequent
                    self.log.debug("Signal ({}) sent via gateway communication port.".format(signum))
                return None
            except Exception as e:
                if isinstance(e, OSError):
                    if e.errno == errno.ECONNREFUSED and signum == 0:  # Return False since there's no process.
                        return False
                return super(RemoteProcessProxy, self).send_signal(signum)
            finally:
                sock.close()
        else:
            return super(RemoteProcessProxy, self).send_signal(signum)

    def shutdown_listener(self):
        # If a comm port has been established, instruct the listener to shutdown so that proper
        # kernel termination can occur.  If not done, the listener keeps the launcher process
        # active, even after the kernel has terminated, leading to less than graceful terminations.

        if self.comm_port > 0:
            shutdown_request = dict()
            shutdown_request['shutdown'] = 1

            sock = socket(AF_INET, SOCK_STREAM)
            try:
                sock.connect((self.comm_ip, self.comm_port))
                sock.send(json.dumps(shutdown_request).encode(encoding='utf-8'))
                self.log.debug("Shutdown request sent to listener via gateway communication port.")
            except Exception as e:
                self.log.warning("Exception occurred sending listener shutdown to {}:{} for KernelID '{}' "
                                 "(using remote kill): {}".format(self.comm_ip, self.comm_port,
                                                                  self.kernel_id, str(e)))
            finally:
                try:
                    sock.shutdown(SHUT_WR)
                except Exception as e2:
                    self.log.warning("Exception occurred attempting to shutdown communication socket to {}:{} "
                                     "for KernelID '{}' (ignored): {}".format(self.comm_ip, self.comm_port,
                                                                              self.kernel_id, str(e2)))
                sock.close()

            # Also terminate the tunnel process for the communication port - if in play.  Failure to terminate
            # this process results in the kernel (launcher) appearing to remain alive following the shutdown
            # request, which triggers the "forced kill" termination logic.

            comm_port_name = KernelChannel.COMMUNICATION.value
            comm_port_tunnel = self.tunnel_processes.get(comm_port_name, None)
            if comm_port_tunnel:
                self.log.debug("shutdown_listener: terminating {} tunnel process.".format(comm_port_name))
                comm_port_tunnel.terminate()
                del self.tunnel_processes[comm_port_name]

    def get_process_info(self):
        process_info = super(RemoteProcessProxy, self).get_process_info()
        process_info.update({'assigned_ip': self.assigned_ip,
                             'assigned_host': self.assigned_host,
                             'comm_ip': self.comm_ip,
                             'comm_port': self.comm_port,
                             'tunneled_connect_info': self.tunneled_connect_info})
        return process_info

    def load_process_info(self, process_info):
        super(RemoteProcessProxy, self).load_process_info(process_info)
        self.assigned_ip = process_info['assigned_ip']
        self.assigned_host = process_info['assigned_host']
        self.comm_ip = process_info['comm_ip']
        self.comm_port = process_info['comm_port']
        if 'tunneled_connect_info' in process_info and process_info['tunneled_connect_info'] is not None:
            # If this was a tunneled connection, re-establish tunnels.  Note, this will reset the
            # communication socket (comm_ip, comm_port) members as well.
            self._setup_connection_info(process_info['tunneled_connect_info'])

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
