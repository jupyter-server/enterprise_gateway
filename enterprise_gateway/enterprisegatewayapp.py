# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Enterprise Gateway Jupyter application."""

import os
import signal
import getpass

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from traitlets import default, List, Set, Unicode, Type, Instance, Bool, Integer

from kernel_gateway.gatewayapp import KernelGatewayApp

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

from tornado.log import LogFormatter

from ._version import __version__
from jupyter_client.kernelspec import KernelSpecManager
from notebook.services.kernels.kernelmanager import MappingKernelManager
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
    remote_hosts_default_value = 'localhost'
    remote_hosts = List(default_value=[remote_hosts_default_value], config=True,
        help="""Bracketed comma-separated list of hosts on which DistributedProcessProxy kernels will be launched
          e.g., ['host1','host2']. (EG_REMOTE_HOSTS env var - non-bracketed, just comma-separated)""")

    @default('remote_hosts')
    def remote_hosts_default(self):
        return os.getenv(self.remote_hosts_env, self.remote_hosts_default_value).split(',')

    # Yarn endpoint
    yarn_endpoint_env = 'EG_YARN_ENDPOINT'
    yarn_endpoint_default_value = 'http://localhost:8088/ws/v1/cluster'
    yarn_endpoint = Unicode(yarn_endpoint_default_value, config=True,
        help="""The http url for accessing the Yarn Resource Manager. (EG_YARN_ENDPOINT env var)""")

    @default('yarn_endpoint')
    def yarn_endpoint_default(self):
        return os.getenv(self.yarn_endpoint_env, self.yarn_endpoint_default_value)

    # Conductor endpoint
    conductor_endpoint_env = 'EG_CONDUCTOR_ENDPOINT'
    conductor_endpoint_default_value = None
    conductor_endpoint = Unicode(conductor_endpoint_default_value, config=True,
        help="""The http url for accessing the Conductor REST API. (EG_CONDUCTOR_ENDPOINT env var)""")

    @default('conductor_endpoint')
    def conductor_endpoint_default(self):
        return os.getenv(self.conductor_endpoint_env, self.conductor_endpoint_default_value)

    _log_formatter_cls = LogFormatter

    @default('log_format')
    def _default_log_format(self):
        """override default log format to include milliseconds"""
        return u"%(color)s[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s]%(end_color)s %(message)s"

    # Impersonation enabled
    impersonation_enabled_env = 'EG_IMPERSONATION_ENABLED'
    impersonation_enabled = Bool(False, config=True,
        help="""Indicates whether impersonation will be performed during kernel launch. 
        (EG_IMPERSONATION_ENABLED env var)""")

    @default('impersonation_enabled')
    def impersonation_enabled_default(self):
        return bool(os.getenv(self.impersonation_enabled_env, 'false').lower() == 'true')

    # Unauthorized users
    unauthorized_users_env = 'EG_UNAUTHORIZED_USERS'
    unauthorized_users_default_value = 'root'
    unauthorized_users = Set(default_value={unauthorized_users_default_value}, config=True,
        help="""Comma-separated list of user names (e.g., ['root','admin']) against which KERNEL_USERNAME
        will be compared.  Any match (case-sensitive) will prevent the kernel's launch
        and result in an HTTP 403 (Forbidden) error. (EG_UNAUTHORIZED_USERS env var - non-bracketed, just
        comma-separated)""")

    @default('unauthorized_users')
    def unauthorized_users_default(self):
        return os.getenv(self.unauthorized_users_env, self.unauthorized_users_default_value).split(',')

    # Authorized users
    authorized_users_env = 'EG_AUTHORIZED_USERS'
    authorized_users = Set(config=True,
        help="""Comma-separated list of user names (e.g., ['bob','alice']) against which KERNEL_USERNAME
        will be compared.  Any match (case-sensitive) will allow the kernel's launch, otherwise an HTTP 403
        (Forbidden) error will be raised.  The set of unauthorized users takes precedence. This option should
        be used carefully as it can dramatically limit who can launch kernels.  (EG_AUTHORIZED_USERS
        env var - non-bracketed, just comma-separated)""")

    @default('authorized_users')
    def authorized_users_default(self):
        au_env = os.getenv(self.authorized_users_env)
        return au_env.split(',') if au_env is not None else []

    # Port range
    port_range_env = 'EG_PORT_RANGE'
    port_range_default_value = "0..0"
    port_range = Unicode(port_range_default_value, config=True,
        help="""Specifies the lower and upper port numbers from which ports are created.  The bounded values
        are separated by '..' (e.g., 33245..34245 specifies a range of 1000 ports to be randomly selected).
        A range of zero (e.g., 33245..33245 or 0..0) disables port-range enforcement.  (EG_PORT_RANGE env var)""")

    @default('port_range')
    def port_range_default(self):
        return os.getenv(self.port_range_env, self.port_range_default_value)

    # Max Kernels per User
    max_kernels_per_user_env = 'EG_MAX_KERNELS_PER_USER'
    max_kernels_per_user_default_value = -1
    max_kernels_per_user = Integer(max_kernels_per_user_default_value, config=True,
        help="""Specifies the maximum number of kernels a user can have active simultaneously.  A value of -1 disables
        enforcement.  (EG_MAX_KERNELS_PER_USER env var)""")

    @default('max_kernels_per_user')
    def max_kernels_per_user_default(self):
        return int(os.getenv(self.max_kernels_per_user_env, self.max_kernels_per_user_default_value))

    kernel_spec_manager = Instance(RemoteKernelSpecManager, allow_none=True)

    kernel_spec_manager_class = Type(
        klass=KernelSpecManager,
        default_value=RemoteKernelSpecManager,
        config=True,
        help="""
        The kernel spec manager class to use. Should be a subclass
        of `jupyter_client.kernelspec.KernelSpecManager`.
        """
    )

    kernel_manager_class = Type(
        klass=MappingKernelManager,
        default_value=RemoteMappingKernelManager,
        config=True,
        help="""
        The kernel manager class to use. Should be a subclass
        of `notebook.services.kernels.MappingKernelManager`.
        """
    )

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

        self.kernel_spec_manager = self.kernel_spec_manager_class(
            parent = self,
        )

        self.kernel_manager = self.kernel_manager_class(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs
        )

        # Detect older version of notebook
        func = getattr(self.kernel_manager, 'initialize_culler', None)
        if not func:
            self.log.warning("Older version of Notebook detected - idle kernels will not be culled.  "
                             "Culling requires Notebook >= 5.1.0.")

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
        # If impersonation is enabled, issue a warning message if the gateway user is not in unauthorized_users.
        if self.impersonation_enabled:
            gateway_user = getpass.getuser()
            if gateway_user.lower() not in self.unauthorized_users:
                self.log.warning("Impersonation is enabled and gateway user '{}' is NOT specified in the set of"
                                 "unauthorized users!  Kernels may execute as that user with elevated privileges.".
                                 format(gateway_user))

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
