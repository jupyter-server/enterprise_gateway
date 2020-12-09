# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel managers that operate against a remote process."""

import abc
import asyncio
import base64
import errno
import getpass
import json
import logging
import os
import paramiko
import pexpect
import random
import re
import signal
import subprocess
import sys
import time

from enum import Enum
from socket import timeout, socket, gethostbyname, gethostname, AF_INET, SOCK_STREAM, SHUT_RDWR, SHUT_WR
from tornado import web
from calendar import timegm
from ipython_genutils.py3compat import with_metaclass
from jupyter_client import launch_kernel, localinterfaces
from notebook import _tz
from zmq.ssh import tunnel

try:
    from Cryptodome.Cipher import AES
except ImportError:
    from Crypto.Cipher import AES

from ..sessions.kernelsessionmanager import KernelSessionManager

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
response_ip = os.getenv('EG_RESPONSE_IP', None)

# Minimum port range size and max retries
min_port_range_size = int(os.getenv('EG_MIN_PORT_RANGE_SIZE', '1000'))
max_port_range_retries = int(os.getenv('EG_MAX_PORT_RANGE_RETRIES', '5'))

# Number of seconds in 100 years as the max keep-alive interval value.
max_keep_alive_interval = 100 * 365 * 24 * 60 * 60

# These envs are not documented and should default to current user and None, respectively.  These
# exist just in case we find them necessary in some configurations (where the service user
# must be different).  However, tests show that that configuration doesn't work - so there
# might be more to do.  At any rate, we'll use these variables for now.
remote_user = None
remote_pwd = None

# Allow users to specify local ips (regular expressions can be used) that should not be included
# when determining the response address.  For example, on systems with many network interfaces,
# some may have their IPs appear the local interfaces list (e.g., docker's 172.17.0.* is an example)
# that should not be used.  This env can be used to indicate such IPs.
prohibited_local_ips = os.getenv('EG_PROHIBITED_LOCAL_IPS', '').split(',')


def _get_local_ip():
    """
    Honor the prohibited IPs, locating the first not in the list.
    """
    for ip in localinterfaces.public_ips():
        is_prohibited = False
        for prohibited_ip in prohibited_local_ips:  # exhaust prohibited list, applying regexs
            if re.match(prohibited_ip, ip):
                is_prohibited = True
                break
        if not is_prohibited:
            return ip
    return localinterfaces.public_ips()[0]  # all were prohibited, so go with the first


local_ip = _get_local_ip()

random.seed()


class KernelChannel(Enum):
    """
    Enumeration used to better manage tunneling
    """
    SHELL = "SHELL"
    IOPUB = "IOPUB"
    STDIN = "STDIN"
    HEARTBEAT = "HB"
    CONTROL = "CONTROL"
    COMMUNICATION = "EG_COMM"  # Optional channel for remote launcher to issue interrupts - NOT a ZMQ channel


class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """
    Process Proxy Abstract Base Class.

    Defines the required methods for process proxy classes.  Some implementation is also performed
    by these methods - common to all subclasses.
    """

    def __init__(self, kernel_manager, proxy_config):
        """
        Initialize the process proxy instance.

        Parameters
        ----------
        kernel_manager : RemoteKernelManager
            The kernel manager instance tied to this process proxy.  This drives the process proxy method calls.

        proxy_config: dict
            The dictionary of per-kernel config settings.  If none are specified, this will be an empty dict.
        """
        self.kernel_manager = kernel_manager
        self.proxy_config = proxy_config
        # Initialize to 0 IP primarily so restarts of remote kernels don't encounter local-only enforcement during
        # relaunch (see jupyter_client.manager.start_kernel().
        self.kernel_manager.ip = '0.0.0.0'
        self.log = kernel_manager.log

        # extract the kernel_id string from the connection file and set the KERNEL_ID environment variable
        if self.kernel_manager.kernel_id is None:
            self.kernel_manager.kernel_id = os.path.basename(self.kernel_manager.connection_file). \
                replace('kernel-', '').replace('.json', '')

        self.kernel_id = self.kernel_manager.kernel_id
        self.kernel_launch_timeout = default_kernel_launch_timeout
        self.lower_port = 0
        self.upper_port = 0
        self._validate_port_range()

        # Handle authorization sets...
        # Take union of unauthorized users...
        self.unauthorized_users = self.kernel_manager.unauthorized_users
        if proxy_config.get('unauthorized_users'):
            self.unauthorized_users = self.unauthorized_users.union(proxy_config.get('unauthorized_users').split(','))

        # Let authorized users override global value - if set on kernelspec...
        if proxy_config.get('authorized_users'):
            self.authorized_users = set(proxy_config.get('authorized_users').split(','))
        else:
            self.authorized_users = self.kernel_manager.authorized_users

        # Represents the local process (from popen) if applicable.  Note that we could have local_proc = None even when
        # the subclass is a LocalProcessProxy (or YarnProcessProxy).  This will happen if EG is restarted and the
        # persisted kernel-sessions indicate that its now running on a different server.  In those cases, we use the ip
        # member variable to determine if the persisted state is local or remote and use signals with the pid to
        # implement the poll, kill and send_signal methods.  As a result, what was a local kernel with one EG instance
        # could be a remote kernel in a restarted EG instance - and vice versa.
        self.local_proc = None
        self.ip = None
        self.pid = 0
        self.pgid = 0

    @abc.abstractmethod
    async def launch_process(self, kernel_cmd, **kwargs):
        """
        Provides basic implementation for launching the process corresponding to the process proxy.

        All overrides should call this method via `super()` so that basic/common operations can be
        performed.  Leaf class implementations are required to perform the actual process launch
        depending on the type of process proxy.

        Parameters
        ----------
        kernel_cmd : str
            The properly formatted string composed from the argv stanza of the kernelspec with
            all curly-braced substitutions performed.

        kwargs : optional
            Additional arguments used during the launch - primarily the env to use for the kernel.
        """
        env_dict = kwargs.get('env')
        if env_dict is None:
            env_dict = dict(os.environ.copy())
            kwargs.update({'env': env_dict})

        # see if KERNEL_LAUNCH_TIMEOUT was included from user.  If so, override default
        if env_dict.get('KERNEL_LAUNCH_TIMEOUT'):
            self.kernel_launch_timeout = float(env_dict.get('KERNEL_LAUNCH_TIMEOUT'))

        # add the applicable kernel_id and language to the env dict
        env_dict['KERNEL_ID'] = self.kernel_id

        kernel_language = 'unknown-kernel-language'
        if len(self.kernel_manager.kernel_spec.language) > 0:
            kernel_language = self.kernel_manager.kernel_spec.language.lower()
        # if already set in env: stanza, let that override.
        env_dict['KERNEL_LANGUAGE'] = env_dict.get('KERNEL_LANGUAGE', kernel_language)

        # Remove any potential sensitive (e.g., passwords) or annoying values (e.g., LG_COLORS)
        for k in env_pop_list:
            env_dict.pop(k, None)

        self._enforce_authorization(**kwargs)

        self.log.debug("BaseProcessProxy.launch_process() env: {}".format(kwargs.get('env')))

    def launch_kernel(self, cmd, **kwargs):
        """
        Returns the result of launching the kernel via Popen.

        This method exists to allow process proxies to perform any final preparations for
        launch, including the removal of any arguments that are not recoginized by Popen.
        """

        # Remove kernel_headers
        kwargs.pop('kernel_headers', None)
        return launch_kernel(cmd, **kwargs)

    def cleanup(self):
        """Performs optional cleanup after kernel is shutdown.  Child classes are responsible for implementations."""
        pass

    def poll(self):
        """
        Determines if process proxy is still alive.

        If this corresponds to a local (popen) process, poll() is called on the subprocess.
        Otherwise, the zero signal is used to determine if active.
        """
        if self.local_proc:
            return self.local_proc.poll()

        return self.send_signal(0)

    def wait(self):
        """
        Wait for the process to become inactive.
        """
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
        """
        Send signal `signum` to process proxy.

        Parameters
        ----------
        signum : int
            The signal number to send.  Zero is used to determine heartbeat.
        """
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
        """
        Terminate the process proxy process.

        First attempts graceful termination, then forced termination.
        Note that this should only be necessary if the message-based kernel termination has
        proven unsuccessful.
        """
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
        """
        Gracefully terminate the process proxy process.

        Note that this should only be necessary if the message-based kernel termination has
        proven unsuccessful.
        """
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
        """
        Returns True if `ip` is considered local to this server, False otherwise.
        """
        return localinterfaces.is_public_ip(ip) or localinterfaces.is_local_ip(ip)

    def _get_ssh_client(self, host):
        """
        Create a SSH Client based on host, username and password if provided.
        If there is any AuthenticationException/SSHException, raise HTTP Error 403 as permission denied.

        :param host:
        :return: ssh client instance
        """
        ssh = None

        global remote_user
        global remote_pwd
        if remote_user is None:
            remote_user = os.getenv('EG_REMOTE_USER', getpass.getuser())
            remote_pwd = os.getenv('EG_REMOTE_PWD')  # this should use password-less ssh

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
        """
        Executes a command on a remote host using ssh.

        Parameters
        ----------
        host : str
            The host on which the command is executed.
        command : str
            The command to execute.

        Returns
        -------
        lines : List
            The command's output.  If stdout is zero length, the stderr output is returned.
        """
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
        """
        Sends signal `signum` to process proxy on remote host.
        """
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
        """
        Sends signal `signum` to local process.
        """
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

    def _enforce_authorization(self, **kwargs):
        """
        Applies any authorization configuration using the kernel user.

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
        env_dict = kwargs.get('env')

        # Although it may already be set in the env, just override in case it was only set via command line or config
        # Convert to string since execve() (called by Popen in base classes) wants string values.
        env_dict['EG_IMPERSONATION_ENABLED'] = str(self.kernel_manager.impersonation_enabled)

        # Ensure KERNEL_USERNAME is set
        kernel_username = KernelSessionManager.get_kernel_username(**kwargs)

        # Now perform authorization checks
        if kernel_username in self.unauthorized_users:
            self._raise_authorization_error(kernel_username, "not authorized")

        # If authorized users are non-empty, ensure user is in that set.
        if self.authorized_users.__len__() > 0:
            if kernel_username not in self.authorized_users:
                self._raise_authorization_error(kernel_username, "not in the set of users authorized")

    def _raise_authorization_error(self, kernel_username, differentiator_clause):
        """
        Raises a 403 status code after building the appropriate message.
        """
        kernel_name = self.kernel_manager.kernel_spec.display_name
        kernel_clause = " '{}'.".format(kernel_name) if kernel_name is not None else "s."
        error_message = "User '{}' is {} to start kernel{} " \
                        "Ensure KERNEL_USERNAME is set to an appropriate value and retry the request.". \
            format(kernel_username, differentiator_clause, kernel_clause)
        self.log_and_raise(http_status_code=403, reason=error_message)

    def get_process_info(self):
        """
        Captures the base information necessary for kernel persistence relative to process proxies.

        The superclass method must always be called first to ensure proper ordering.  Since this is the
        most base class, no call to `super()` is necessary.
        """
        process_info = {'pid': self.pid, 'pgid': self.pgid, 'ip': self.ip}
        return process_info

    def load_process_info(self, process_info):
        """
        Loads the base information necessary for kernel persistence relative to process proxies.

        The superclass method must always be called first to ensure proper ordering.  Since this is the
        most base class, no call to `super()` is necessary.
        """
        self.pid = process_info['pid']
        self.pgid = process_info['pgid']
        self.ip = process_info['ip']
        self.kernel_manager.ip = process_info['ip']

    def _validate_port_range(self):
        """
        Validates the port range configuration option to ensure appropriate values.
        """
        # Let port_range override global value - if set on kernelspec...
        port_range = self.kernel_manager.port_range
        if self.proxy_config.get('port_range'):
            port_range = self.proxy_config.get('port_range')

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
        """
        Selects and returns n random ports that adhere to the configured port range, if applicable.

        Parameters
        ----------
        count : int
            The number of ports to return

        Returns
        -------
        List - ports available and adhering to the configured port range
        """
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
        """
        Creates and returns a socket whose port adheres to the configured port range, if applicable.

        Parameters
        ----------
        ip : str
            Optional ip address to which the port is bound

        Returns
        -------
        socket - Bound socket that is available and adheres to configured port range
        """
        sock = socket(AF_INET, SOCK_STREAM)
        found_port = False
        retries = 0
        while not found_port:
            try:
                sock.bind((ip, self._get_candidate_port()))
                found_port = True
            except Exception:
                retries = retries + 1
                if retries > max_port_range_retries:
                    self.log_and_raise(http_status_code=500, reason="Failed to locate port within range {} after {} "
                                       "retries!".format(self.kernel_manager.port_range, max_port_range_retries))
        return sock

    def _get_candidate_port(self):
        """Randomly selects a port number within the configured range.

        If no range is configured, the 0 port is used - allowing the server to choose from the full range.
        """
        range_size = self.upper_port - self.lower_port
        if range_size == 0:
            return 0
        return random.randint(self.lower_port, self.upper_port)

    def log_and_raise(self, http_status_code=None, reason=None):
        """
        Helper method that combines the logging and raising of exceptions.

        If http_status_code is provided an HTTPError is created using the status code and
        reason.  If http_status_code is not provided, a RuntimeError is raised with reason
        as the message.  In either case, an error is logged using the reason.  If reason is
        not provided a generic message will be used.
        Parameters
        ----------
        http_status_code : int
            The status code to raise
        reason : str
            The message to log and associate with the exception
        """
        if reason is None:
            reason = "Internal server issue!"

        self.log.error(reason)
        if http_status_code:
            raise web.HTTPError(status_code=http_status_code, reason=reason)
        else:
            raise RuntimeError(reason)


class LocalProcessProxy(BaseProcessProxyABC):
    """
    Manages the lifecycle of a locally launched kernel process.

    This process proxy is used when no other process proxy is configured.
    """
    def __init__(self, kernel_manager, proxy_config):
        super(LocalProcessProxy, self).__init__(kernel_manager, proxy_config)
        kernel_manager.ip = localinterfaces.LOCALHOST

    async def launch_process(self, kernel_cmd, **kwargs):
        await super(LocalProcessProxy, self).launch_process(kernel_cmd, **kwargs)

        # launch the local run.sh
        self.local_proc = self.launch_kernel(kernel_cmd, **kwargs)
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
    """
    Abstract Base Class implementation associated with remote process proxies.
    """

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

    async def launch_process(self, kernel_cmd, **kwargs):
        # Pass along port-range info to kernels...
        kwargs['env']['EG_MIN_PORT_RANGE_SIZE'] = str(min_port_range_size)
        kwargs['env']['EG_MAX_PORT_RANGE_RETRIES'] = str(max_port_range_retries)

        await super(RemoteProcessProxy, self).launch_process(kernel_cmd, **kwargs)
        # remove connection file because a) its not necessary any longer since launchers will return
        # the connection information which will (sufficiently) remain in memory and b) launchers
        # landing on this node may want to write to this file and be denied access.
        self.kernel_manager.cleanup_connection_file()

    @abc.abstractmethod
    def confirm_remote_startup(self):
        """Confirms the remote process has started and returned necessary connection information."""
        pass

    def detect_launch_failure(self):
        """
        Helper method called from implementations of `confirm_remote_startup()` that checks if
        self.local_proc (a popen instance) has terminated prior to the confirmation of startup.
        This prevents users from having to wait for the kernel timeout duration to know if the
        launch fails.  It also helps distinguish local invocation issues from remote post-launch
        issues since the failure will be relatively immediate.

        Note that this method only applies to those process proxy implementations that launch
        from the local node.  Proxies like DistributedProcessProxy use rsh against a remote
        node, so there's not `local_proc` in play to interrogate.
        """

        # Check if the local proc has faulted (poll() will return non-None with a non-zero return
        # code in such cases).  If a fault was encountered, raise server error (500) with a message
        # indicating to check the EG log for more information.
        if self.local_proc:
            poll_result = self.local_proc.poll()
            if poll_result and poll_result > 0:
                self.local_proc.wait()
                error_message = "Error occurred during launch of KernelID: {}.  " \
                                "Check Enterprise Gateway log for more information.".format(self.kernel_id)
                self.local_proc = None
                self.log_and_raise(http_status_code=500, reason=error_message)

    def _prepare_response_socket(self):
        """
        Prepares the response socket on which connection info arrives from remote kernel launcher.
        """
        s = self.select_socket(local_ip)
        port = s.getsockname()[1]
        s.listen(1)
        s.settimeout(socket_timeout)
        self.kernel_manager.response_address = (local_ip if response_ip is None else response_ip) + ':' + str(port)
        self.log.debug("Response socket launched on '{}' using {}s timeout".
                       format(self.kernel_manager.response_address, socket_timeout))
        self.response_socket = s

    def _tunnel_to_kernel(self, connection_info, server, port=ssh_port, key=None):
        """
        Tunnel connections to a kernel over SSH

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
        """
        Analogous to _tunnel_to_kernel, but deals with a single port.  This will typically be called for
        any one-off ports that require tunnelling. Note - this method assumes that passwordless ssh is
        in use and has been previously validated.
        """
        local_port = self.select_ports(1)[0]
        self._create_ssh_tunnel(kernel_channel, local_port, remote_port, remote_ip, server, port, key)
        return local_port

    def _create_ssh_tunnel(self, kernel_channel, local_port, remote_port, remote_ip, server, port, key):
        """
        Creates an SSH tunnel between the local and remote port/server for the given kernel channel.
        """
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
        """
        This method spawns a child process to create an SSH tunnel and returns the spawned process.
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
        cull_idle_timeout = self.kernel_manager.cull_idle_timeout

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
        # will add 60 seconds to cull_idle_timeout to come up with the value for keep-alive
        # interval for the rest of the kernel channels.  If culling isn't configured, use
        # `max_keep_alive_interval`.
        return cull_idle_timeout + 60 if cull_idle_timeout > 0 else max_keep_alive_interval

    def _decrypt(self, data):
        """
        Decrypts `data` using the kernel_id as the key.
        """
        key = self.kernel_id[0:16]
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
        payload = cipher.decrypt(base64.b64decode(data))
        payload = "".join([payload.decode("utf-8").rsplit("}", 1)[0], "}"])  # Get rid of padding after the '}'.
        return payload

    async def receive_connection_info(self):
        """
        Monitors the response address for connection info sent by the remote kernel launcher.
        """
        # Polls the socket using accept.  When data is found, returns ready indicator and encrypted data.
        ready_to_connect = False
        loop = asyncio.get_event_loop()  # TODO confirm if this should be IOLoop.current() or whatever

        async def get_info(conn):
            data = ''
            while True:
                buffer = await loop.sock_recv(conn, 1024)
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
                    break
                data = data + buffer.decode(encoding='utf-8')  # append what we received until we get no more...
            conn.close()

        async def get_response():
            conn, addr = await loop.sock_accept(self.response_socket)
            await get_info(conn)

        if self.response_socket:
            try:
                await get_response()
                ready_to_connect = True
            except Exception as e:
                if type(e) is timeout:
                    self.log.debug("Waiting for KernelID '{}' to send connection info from host '{}' - retrying..."
                                   .format(self.kernel_id, self.assigned_host))
                else:
                    error_message = "Exception occurred waiting for connection file response for KernelId '{}' "\
                        "on host '{}': {}".format(self.kernel_id, self.assigned_host, str(e))
                    await asyncio.get_event_loop().run_in_executor(None, self.kill)
                    self.log_and_raise(http_status_code=500, reason=error_message)
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

        self._close_response_socket()
        self.kernel_manager._connection_file_written = True  # allows for cleanup of local files (as necessary)

    def _close_response_socket(self):
        # If there's a response-socket, close it since its no longer needed.
        if self.response_socket:
            try:
                self.log.debug("response socket still open, close it")
                self.response_socket.shutdown(SHUT_RDWR)
                self.response_socket.close()
            except OSError:
                pass  # tolerate exceptions here since we don't need this socket and would like ot continue
            self.response_socket = None

    def _extract_pid_info(self, connect_info):
        """
        Extracts any PID, PGID info from the payload received on the response socket.
        """
        pid = connect_info.pop('pid', None)
        if pid:
            try:
                self.pid = int(pid)
            except ValueError:
                self.log.warning("pid returned from kernel launcher is not an integer: {} - ignoring.".format(pid))
                pid = None
        pgid = connect_info.pop('pgid', None)
        if pgid:
            try:
                self.pgid = int(pgid)
            except ValueError:
                self.log.warning("pgid returned from kernel launcher is not an integer: {} - ignoring.".format(pgid))
                pgid = None
        if pid or pgid:  # if either process ids were updated, update the ip as well and don't use local_proc
            self.ip = self.assigned_ip
            if not BaseProcessProxyABC.ip_is_local(self.ip):  # only unset local_proc if we're remote
                self.local_proc = None

    async def handle_timeout(self):
        """
        Checks to see if the kernel launch timeout has been exceeded while awaiting connection info.
        """
        await asyncio.sleep(poll_interval)
        time_interval = RemoteProcessProxy.get_time_diff(self.start_time, RemoteProcessProxy.get_current_time())

        if time_interval > self.kernel_launch_timeout:
            error_http_code = 500
            reason = "Waited too long ({}s) to get connection file".format(self.kernel_launch_timeout)
            timeout_message = "KernelID: '{}' launch timeout due to: {}".format(self.kernel_id, reason)
            await asyncio.get_event_loop().run_in_executor(None, self.kill)
            self.log_and_raise(http_status_code=error_http_code, reason=timeout_message)

    def cleanup(self):
        """
        Terminates tunnel processes, if applicable.
        """
        self.assigned_ip = None

        for kernel_channel, process in self.tunnel_processes.items():
            self.log.debug("cleanup: terminating {} tunnel process.".format(kernel_channel))
            process.terminate()

        self.tunnel_processes.clear()
        super(RemoteProcessProxy, self).cleanup()

    def _send_listener_request(self, request, shutdown_socket=False):
        """
        Sends the request dictionary to the kernel listener via the comm port.  Caller is responsible for
        handling any exceptions.
        """

        if self.comm_port > 0:
            sock = socket(AF_INET, SOCK_STREAM)
            try:
                sock.settimeout(socket_timeout)
                sock.connect((self.comm_ip, self.comm_port))
                sock.send(json.dumps(request).encode(encoding='utf-8'))
            finally:
                if shutdown_socket:
                    try:
                        sock.shutdown(SHUT_WR)
                    except Exception as e2:
                        if isinstance(e2, OSError) and e2.errno == errno.ENOTCONN:
                            pass  # Listener is not connected.  This is probably a follow-on to ECONNREFUSED on connect
                        else:
                            self.log.warning("Exception occurred attempting to shutdown communication socket to {}:{} "
                                             "for KernelID '{}' (ignored): {}".format(self.comm_ip, self.comm_port,
                                                                                      self.kernel_id, str(e2)))
                sock.close()

    def send_signal(self, signum):
        """
        Sends `signum` via the communication port.
        The kernel launcher listening on its communication port will receive the signum and perform
        the necessary signal operation local to the process.
        """
        # If the launcher returned a comm_port value, then use that to send the signal,
        # else, defer to the superclass - which will use a remote shell to issue kill.
        # Note that if the target process is running as a different user than the REMOTE_USER,
        # using anything other than the socket-based signal (via signal_addr) will not work.

        if self.comm_port > 0:
            signal_request = dict()
            signal_request['signum'] = signum

            try:
                self._send_listener_request(signal_request)

                if signum > 0:  # Polling (signum == 0) is too frequent
                    self.log.debug("Signal ({}) sent via gateway communication port.".format(signum))
                return None
            except Exception as e:
                if isinstance(e, OSError) and e.errno == errno.ECONNREFUSED:  # Return False since there's no process.
                    return False

                self.log.warning("An unexpected exception occurred sending signal ({}) for KernelID '{}': {}"
                                 .format(signum, self.kernel_id, str(e)))

        return super(RemoteProcessProxy, self).send_signal(signum)

    def shutdown_listener(self):
        """
        Sends a shutdown request to the kernel launcher listener.
        """
        # If a comm port has been established, instruct the listener to shutdown so that proper
        # kernel termination can occur.  If not done, the listener keeps the launcher process
        # active, even after the kernel has terminated, leading to less than graceful terminations.

        if self.comm_port > 0:
            shutdown_request = dict()
            shutdown_request['shutdown'] = 1

            try:
                self._send_listener_request(shutdown_request, shutdown_socket=True)
                self.log.debug("Shutdown request sent to listener via gateway communication port.")
            except Exception as e:
                if not isinstance(e, OSError) or e.errno != errno.ECONNREFUSED:
                    self.log.warning("An unexpected exception occurred sending listener shutdown to {}:{} for "
                                     "KernelID '{}': {}"
                                     .format(self.comm_ip, self.comm_port, self.kernel_id, str(e)))

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
        """
        Captures the base information necessary for kernel persistence relative to remote processes.
        """
        process_info = super(RemoteProcessProxy, self).get_process_info()
        process_info.update({'assigned_ip': self.assigned_ip,
                             'assigned_host': self.assigned_host,
                             'comm_ip': self.comm_ip,
                             'comm_port': self.comm_port,
                             'tunneled_connect_info': self.tunneled_connect_info})
        return process_info

    def load_process_info(self, process_info):
        """
        Captures the base information necessary for kernel persistence relative to remote processes.
        """
        super(RemoteProcessProxy, self).load_process_info(process_info)
        self.assigned_ip = process_info['assigned_ip']
        self.assigned_host = process_info['assigned_host']
        self.comm_ip = process_info['comm_ip']
        self.comm_port = process_info['comm_port']
        if 'tunneled_connect_info' in process_info and process_info['tunneled_connect_info'] is not None:
            # If this was a tunneled connection, re-establish tunnels.  Note, this will reset the
            # communication socket (comm_ip, comm_port) members as well.
            self._setup_connection_info(process_info['tunneled_connect_info'])

    def log_and_raise(self, http_status_code=None, reason=None):
        """
        Override log_and_raise method in order to verify that the response socket is properly closed
        before raise exception
        """
        self._close_response_socket()
        super().log_and_raise(http_status_code, reason)

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
