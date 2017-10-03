# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Enterprise Gateway Jupyter application."""

import os
import signal

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from traitlets import default, List, Unicode

from kernel_gateway.gatewayapp import KernelGatewayApp

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

from tornado.log import LogFormatter

from ._version import __version__
from kernel_gateway.services.sessions.sessionmanager import SessionManager
from .services.sessions.kernelsessionmanager import KernelSessionManager
from .services.kernels.remotemanager import RemoteMappingKernelManager
from .services.kernelspecs.remotekernelspec import RemoteKernelSpecManager


class EnterpriseGatewayApp(KernelGatewayApp):
    """Application that provisions Jupyter kernels and proxies HTTP/Websocket
    traffic to the kernels.

    - reads command line and environment variable settings
    - initializes managers and routes
    - creates a Tornado HTTP server
    - starts the Tornado event loop
    """
    name = 'jupyter-enterprise-gateway'
    version = __version__
    description = """
        Jupyter Enterprise Gateway

        Provisions remote Jupyter kernels and proxies HTTP/Websocket traffic
        to them.
    """

    # Remote hosts
    remote_hosts_env = 'EG_REMOTE_HOSTS'
    remote_hosts_default_value = ['localhost']
    remote_hosts = List(remote_hosts_default_value, config=True,
        help="""Bracketed comma-separated list of hosts on which DistributedProcessProxy kernels will be launched
          e.g., ['host1','host2']. (EG_REMOTE_HOSTS env var - non-bracketed, just comma-separated)""")

    @default('remote_hosts')
    def remote_hosts_default(self):
        return os.getenv(self.remote_hosts_env, 'localhost').split(',')

    # Remote User
    remote_user_env = 'EG_REMOTE_USER'
    remote_user = Unicode(config=True,
        help="""The username used for remote operations (ssh).  Password-less ssh is required. 
        (EG_REMOTE_USER env var)""")

    # if EG_REMOTE_USER is not defined, default to the current USER, else the empty string.
    @default('remote_user')
    def remote_user_default(self):
        return os.getenv(self.remote_user_env, os.getenv('USER', ''))

    # Yarn endpoint
    yarn_endpoint_env = 'EG_YARN_ENDPOINT'
    yarn_endpoint_default_value = 'http://localhost:8088/ws/v1/cluster'
    yarn_endpoint = Unicode(yarn_endpoint_default_value, config=True,
        help="""The http url for accessing the Yarn Resource Manager. (EG_YARN_ENDPOINT env var)""")

    @default('yarn_endpoint')
    def yarn_endpoint_default(self):
        return os.getenv(self.yarn_endpoint_env, self.yarn_endpoint_default_value)

    _log_formatter_cls = LogFormatter

    @default('log_format')
    def _default_log_format(self):
        """override default log format to include milliseconds"""
        return u"%(color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(end_color)s %(message)s"

    def init_configurables(self):
        """Initializes all configurable objects including a kernel manager, kernel
        spec manager, session manager, and personality.

        Any kernel pool configured by the personality will be its responsibility
        to shut down.

        Optionally, loads a notebook and prespawns the configured number of
        kernels.
        """
        self.kernel_spec_manager = RemoteKernelSpecManager(parent=self)

        self.seed_notebook = None
        if self.seed_uri is not None:
            # Note: must be set before instantiating a SeedingMappingKernelManager
            self.seed_notebook = self._load_notebook(self.seed_uri)

        # Only pass a default kernel name when one is provided. Otherwise,
        # adopt whatever default the kernel manager wants to use.
        kwargs = {}
        if self.default_kernel_name:
            kwargs['default_kernel_name'] = self.default_kernel_name

        self.kernel_manager = RemoteMappingKernelManager(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs
        )

        # Detect older version of notebook
        func = getattr(self.kernel_manager, 'initialize_culler', None)
        if not func:
            self.log.warning("Older version of Notebook detected - idle kernels will not be culled.  Culling requires Notebook >= 5.1.0.")

        self.session_manager = SessionManager(
            log=self.log,
            kernel_manager=self.kernel_manager
        )

        self.kernel_session_manager = KernelSessionManager(
            log=self.log,
            kernel_manager=self.kernel_manager,
            config=self.config, # required to get command-line options visible
            **kwargs
        )
        # Attempt to start persisted sessions
        self.kernel_session_manager.start_sessions()

        self.contents_manager = None

        if self.prespawn_count:
            if self.max_kernels and self.prespawn_count > self.max_kernels:
                raise RuntimeError('cannot prespawn {}; more than max kernels {}'.format(
                    self.prespawn_count, self.max_kernels)
                )

        api_module = self._load_api_module(self.api)
        func = getattr(api_module, 'create_personality')
        self.personality = func(parent=self, log=self.log)

        self.personality.init_configurables()

    def start(self):
        """Starts an IO loop for the application. """

        # Note that we *intentionally* reference the KernelGatewayApp so that we bypass
        # its start() logic and just call that of JKG's superclass.
        super(KernelGatewayApp, self).start()
        self.log.info('Jupyter Enterprise Gateway at http{}://{}:{}'.format(
            's' if self.keyfile else '', self.ip, self.port
        ))
        self.io_loop = ioloop.IOLoop.current()

        signal.signal(signal.SIGTERM, self._signal_stop)

        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.log.info("Interrupted...")
            # Ignore further interrupts (ctrl-c)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        finally:
            self.shutdown()

    def stop(self):
        """
        Stops the HTTP server and IO loop associated with the application.
        """
        def _stop():
            self.http_server.stop()
            self.io_loop.stop()
        self.io_loop.add_callback(_stop)

    def _signal_stop(self, sig, frame):
        self.log.info("Received signal to terminate Enterprise Gateway.")
        self.io_loop.stop()

launch_instance = EnterpriseGatewayApp.launch_instance
