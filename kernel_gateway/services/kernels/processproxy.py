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
from ipython_genutils.py3compat import with_metaclass
from socket import *


#
logging.getLogger('paramiko').setLevel(os.getenv('ELYRA_SSH_LOG_LEVEL', logging.WARNING))


class BaseProcessProxyABC(with_metaclass(abc.ABCMeta, object)):
    """Process Proxy ABC.

    Defines the required methods for process proxy classes
    """

    @abc.abstractmethod
    def poll(self):
        pass

    @abc.abstractmethod
    def wait(self):
        pass

    @abc.abstractmethod
    def send_signal(self, signum):
        pass

    @abc.abstractmethod
    def kill(self):
        pass


class StandaloneProcessProxy(BaseProcessProxyABC):

    # FIXME - properly deal with ip, username and password
    ip = os.getenv('ELYRA_REMOTE_HOST', 'localhost')
    username = os.getenv('ELYRA_REMOTE_USER')
    password = os.getenv('ELYRA_REMOTE_PWD')  # this should use password-less ssh
    pid = 0
    kernel_manager = None
    remote_connection_file = None

    def __init__(self, kernel_manager, cmd, **kw):

        self.kernel_manager = kernel_manager
        self.kernel_manager.ip = gethostbyname(self.ip)  # convert to ip if host is provided
        # save off connection file name for cleanup later
        self.remote_connection_file = kernel_manager.remote_connection_file
        # write out connection file - which has the remote IP - prior to copy...
        self.kernel_manager.cleanup_connection_file()
        self.kernel_manager.write_connection_file()

        cmd = self.build_startup_command(cmd)
        self.kernel_manager.log.debug('Invoking cmd: {}'.format(cmd))
        result_pid = 'bad_pid'  # purposely initialize to bad int value
        result = self.rsh(cmd, self.kernel_manager.connection_file, self.kernel_manager.remote_connection_file)
        for line in result:
            result_pid = line.strip()

        try:
            self.pid = int(result_pid)
        except ValueError:
            raise RuntimeError("Failure occurred starting remote kernel on '{}'.  Returned result: {}"
                               .format(self.ip, result))

        self.kernel_manager.log.info("Remote kernel launched on '{}', pid={}"
                                     .format(self.kernel_manager.ip, self.pid))

    def poll(self):
        result = self.remote_signal(0)
        #  self.kernel_manager.log.debug('StandaloneProcessProxy.poll: {}'.format(result))
        return result

    def wait(self):
        poll_interval = 0.2
        wait_time = 5.0
        for i in range(int(wait_time/poll_interval)):
            if self.poll():
                time.sleep(poll_interval)
            else:
                break
        else:
            self.kernel_manager.log.warning("Wait timeout of 5 seconds exhausted.  Continuing...")

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
            cmd += 'export {}={};'.format(key,json.dumps(value))

        # Add additional envs not in kernelspec...
        username = os.getenv('KERNEL_USERNAME')
        if username is not None:
            cmd += 'export KERNEL_USERNAME="{}";'.format(username)

        cmd += 'nohup'
        for arg in argv_cmd:
            cmd += ' {}'.format(arg)

        cmd += ' >> /var/log/jnbg/remote_launch.log 2>&1 & echo $!'

        return cmd

    def rsh(self, command, srcFile=None, dstFile=None):

        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if len(self.password) > 0:
                ssh.connect(self.ip, port=22, username=self.username, password=self.password)
            else:
                ssh.connect(self.ip, port=22, username=self.username)
                
            if srcFile is not None and dstFile is not None:
                try:
                    self.kernel_manager.log.debug("Copying file '{}' to file '{}@{}' ..."
                                                  .format(srcFile, self.ip, dstFile))
                    sftp = ssh.open_sftp()
                    sftp.put(srcFile, dstFile)
                except Exception as e:
                    self.kernel_manager.log.error(
                        "Exception '{}' occurred attempting to copy file '{}' "
                        "to '{}' on '{}' with user '{}', message='{}'"
                        .format(type(e).__name__, srcFile, dstFile, self.ip, self.username, e))
                    raise e

            stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
            lines = stdout.readlines()
            if len(lines) == 0:  # if nothing in stdout, return stderr
                lines = stderr.readlines()

        except Exception as e:
            self.kernel_manager.log.error(
                "Exception '{}' occurred attempting to connect to '{}' with user '{}', message='{}'"
                .format(type(e).__name__, self.ip, self.username, e))
            raise e

        finally:
            if ssh is not None:
                ssh.close()

        return lines


class YarnProcessProxy(BaseProcessProxyABC):

    application_id = None

    def __init__(self,  kernel_manager, kernel_cmd, **kw):
        self.kernel_manager = kernel_manager

        self.pre_launch_kernel(kernel_cmd, **kw)

        self.post_launch_kernel(kernel_cmd, **kw)

    def poll(self):
        self.kernel_manager.log.debug("YarnProcessProxy.poll")

    def wait(self):
        self.kernel_manager.log.debug("YarnProcessProxy.wait")

    def send_signal(self, signum):
        self.kernel_manager.log.debug("YarnProcessProxy.send_signal {}".format(signum))

    def kill(self):
        self.kernel_manager.log.debug("YarnProcessProxy.kill")


    def pre_launch_kernel(self, kernel_cmd, **kw):
        """ Asks Yarn for an application ID and extends kernel_cmd with --yarnAppId parameter that
            run.sh knows how to interpret and use.
        """
        self.kernel_manager.log.debug(
            "YarnProcessProxy.pre_launch_kernel.connection_info: {}"
            .format(self.kernel_manager.get_connection_info()))

        self.get_yarn_application_id(kernel_cmd, **kw)
        # PROTOTYPE - HOOK UP ELYRA to REMOTE KERNEL...
        self.kernel_manager.ip = gethostbyname(os.getenv('ELYRA_REMOTE_HOST', 'fwiw1.fyre.ibm.com'))
        self.kernel_manager.stdin_port = int(os.getenv('ELYRA_TEST_RM_STDIN', '56759'))
        self.kernel_manager.iopub_port = int(os.getenv('ELYRA_TEST_RM_IOPUB', '56758'))
        self.kernel_manager.shell_port = int(os.getenv('ELYRA_TEST_RM_SHELL', '56757'))
        self.kernel_manager.hb_port = int(os.getenv('ELYRA_TEST_RM_HB', '56761'))
        self.kernel_manager.control_port = int(os.getenv('ELYRA_TEST_RM_CONTROL', '56760'))
        self.kernel_manager.session.key = b'' # FIXME

    def post_launch_kernel(self, kernel_cmd, **kw):
        self.kernel_manager.log.debug(
            "YarnProcessProxy.post_launch_kernel.connection_info: {}"
            .format(self.kernel_manager.get_connection_info()))


    def get_yarn_application_id(self, kernel_cmd, **kw):
        """
        Invokes the Yarn API to obtain a new application id that will be conveyed to the kernel when
        launching cluster-managed kernel.
        """
        if self.application_id is None:
            self.application_id = os.getenv('ELYRA_TEST_APP_ID', 'application_1492445751293_0018')

        if kernel_cmd is not None:
            kernel_cmd.extend(['--yarnAppId', self.application_id])

        return self.application_id
