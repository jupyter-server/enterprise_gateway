# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Enterprise Gateway Jupyter application."""

import errno
import getpass
import logging
import os
import signal
import socket
import sys
import time
import weakref

from distutils.util import strtobool

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

from tornado import httpserver
from tornado import web
from tornado.log import enable_pretty_logging, LogFormatter

from traitlets import default, List, Set, Unicode, Type, Instance, Bool, CBool, Integer, observe
from traitlets.config import Configurable
from jupyter_core.application import JupyterApp, base_aliases
from jupyter_client.kernelspec import KernelSpecManager
from notebook.services.kernels.kernelmanager import MappingKernelManager
from notebook.notebookapp import random_ports
from notebook.utils import url_path_join

from ._version import __version__

from .base.handlers import default_handlers as default_base_handlers
from .services.api.handlers import default_handlers as default_api_handlers
from .services.kernels.handlers import default_handlers as default_kernel_handlers
from .services.kernelspecs.handlers import default_handlers as default_kernelspec_handlers
from .services.sessions.handlers import default_handlers as default_session_handlers

from .services.sessions.kernelsessionmanager import KernelSessionManager, FileKernelSessionManager
from .services.sessions.sessionmanager import SessionManager
from .services.kernels.remotemanager import RemoteMappingKernelManager


# Add additional command line aliases
aliases = dict(base_aliases)
aliases.update({
    'ip': 'EnterpriseGatewayApp.ip',
    'port': 'EnterpriseGatewayApp.port',
    'port_retries': 'EnterpriseGatewayApp.port_retries',
    'keyfile': 'EnterpriseGatewayApp.keyfile',
    'certfile': 'EnterpriseGatewayApp.certfile',
    'client-ca': 'EnterpriseGatewayApp.client_ca'
})


class EnterpriseGatewayApp(JupyterApp):
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

        Provisions remote Jupyter kernels and proxies HTTP/Websocket traffic to them.
    """

    # Also include when generating help options
    classes = [FileKernelSessionManager, RemoteMappingKernelManager]

    # Enable some command line shortcuts
    aliases = aliases

    # Server IP / PORT binding
    port_env = 'EG_PORT'
    port_default_value = 8888
    port = Integer(port_default_value, config=True,
                   help='Port on which to listen (EG_PORT env var)')

    @default('port')
    def port_default(self):
        return int(os.getenv(self.port_env, os.getenv('KG_PORT', self.port_default_value)))

    port_retries_env = 'EG_PORT_RETRIES'
    port_retries_default_value = 50
    port_retries = Integer(port_retries_default_value, config=True,
                           help="""Number of ports to try if the specified port is not available
                           (EG_PORT_RETRIES env var)""")

    @default('port_retries')
    def port_retries_default(self):
        return int(os.getenv(self.port_retries_env, os.getenv('KG_PORT_RETRIES', self.port_retries_default_value)))

    ip_env = 'EG_IP'
    ip_default_value = '127.0.0.1'
    ip = Unicode(ip_default_value, config=True,
                 help='IP address on which to listen (EG_IP env var)')

    @default('ip')
    def ip_default(self):
        return os.getenv(self.ip_env, os.getenv('KG_IP', self.ip_default_value))

    # Base URL
    base_url_env = 'EG_BASE_URL'
    base_url_default_value = '/'
    base_url = Unicode(base_url_default_value, config=True,
                       help='The base path for mounting all API resources (EG_BASE_URL env var)')

    @default('base_url')
    def base_url_default(self):
        return os.getenv(self.base_url_env, os.getenv('KG_BASE_URL', self.base_url_default_value))

    # Token authorization
    auth_token_env = 'EG_AUTH_TOKEN'
    auth_token = Unicode(config=True,
                         help='Authorization token required for all requests (EG_AUTH_TOKEN env var)')

    @default('auth_token')
    def _auth_token_default(self):
        return os.getenv(self.auth_token_env, os.getenv('KG_AUTH_TOKEN', ''))

    # Begin CORS headers
    allow_credentials_env = 'EG_ALLOW_CREDENTIALS'
    allow_credentials = Unicode(config=True,
                                help='Sets the Access-Control-Allow-Credentials header. (EG_ALLOW_CREDENTIALS env var)')

    @default('allow_credentials')
    def allow_credentials_default(self):
        return os.getenv(self.allow_credentials_env, os.getenv('KG_ALLOW_CREDENTIALS', ''))

    allow_headers_env = 'EG_ALLOW_HEADERS'
    allow_headers = Unicode(config=True,
                            help='Sets the Access-Control-Allow-Headers header. (EG_ALLOW_HEADERS env var)')

    @default('allow_headers')
    def allow_headers_default(self):
        return os.getenv(self.allow_headers_env, os.getenv('KG_ALLOW_HEADERS', ''))

    allow_methods_env = 'EG_ALLOW_METHODS'
    allow_methods = Unicode(config=True,
                            help='Sets the Access-Control-Allow-Methods header. (EG_ALLOW_METHODS env var)')

    @default('allow_methods')
    def allow_methods_default(self):
        return os.getenv(self.allow_methods_env, os.getenv('KG_ALLOW_METHODS', ''))

    allow_origin_env = 'EG_ALLOW_ORIGIN'
    allow_origin = Unicode(config=True,
                           help='Sets the Access-Control-Allow-Origin header. (EG_ALLOW_ORIGIN env var)')

    @default('allow_origin')
    def allow_origin_default(self):
        return os.getenv(self.allow_origin_env, os.getenv('KG_ALLOW_ORIGIN', ''))

    expose_headers_env = 'EG_EXPOSE_HEADERS'
    expose_headers = Unicode(config=True,
                             help='Sets the Access-Control-Expose-Headers header. (EG_EXPOSE_HEADERS env var)')

    @default('expose_headers')
    def expose_headers_default(self):
        return os.getenv(self.expose_headers_env, os.getenv('KG_EXPOSE_HEADERS', ''))

    trust_xheaders_env = 'EG_TRUST_XHEADERS'
    trust_xheaders = CBool(False, config=True,
                           help="""Use x-* header values for overriding the remote-ip, useful when
                           application is behing a proxy. (EG_TRUST_XHEADERS env var)""")

    @default('trust_xheaders')
    def trust_xheaders_default(self):
        return strtobool(os.getenv(self.trust_xheaders_env, os.getenv('KG_TRUST_XHEADERS', 'False')))

    certfile_env = 'EG_CERTFILE'
    certfile = Unicode(None, config=True, allow_none=True,
                       help='The full path to an SSL/TLS certificate file. (EG_CERTFILE env var)')

    @default('certfile')
    def certfile_default(self):
        return os.getenv(self.certfile_env, os.getenv('KG_CERTFILE'))

    keyfile_env = 'EG_KEYFILE'
    keyfile = Unicode(None, config=True, allow_none=True,
                      help='The full path to a private key file for usage with SSL/TLS. (EG_KEYFILE env var)')

    @default('keyfile')
    def keyfile_default(self):
        return os.getenv(self.keyfile_env, os.getenv('KG_KEYFILE'))

    client_ca_env = 'EG_CLIENT_CA'
    client_ca = Unicode(None, config=True, allow_none=True,
                        help="""The full path to a certificate authority certificate for SSL/TLS
                        client authentication. (EG_CLIENT_CA env var)""")

    @default('client_ca')
    def client_ca_default(self):
        return os.getenv(self.client_ca_env, os.getenv('KG_CLIENT_CA'))

    max_age_env = 'EG_MAX_AGE'
    max_age = Unicode(config=True,
                      help='Sets the Access-Control-Max-Age header. (EG_MAX_AGE env var)')

    @default('max_age')
    def max_age_default(self):
        return os.getenv(self.max_age_env, os.getenv('KG_MAX_AGE', ''))
    # End CORS headers

    max_kernels_env = 'EG_MAX_KERNELS'
    max_kernels = Integer(None, config=True,
                          allow_none=True,
                          help="""Limits the number of kernel instances allowed to run by this gateway.
                          Unbounded by default. (EG_MAX_KERNELS env var)""")

    @default('max_kernels')
    def max_kernels_default(self):
        val = os.getenv(self.max_kernels_env, os.getenv('KG_MAX_KERNELS'))
        return val if val is None else int(val)

    default_kernel_name_env = 'EG_DEFAULT_KERNEL_NAME'
    default_kernel_name = Unicode(config=True,
                                  help='Default kernel name when spawning a kernel (EG_DEFAULT_KERNEL_NAME env var)')

    @default('default_kernel_name')
    def default_kernel_name_default(self):
        # defaults to Jupyter's default kernel name on empty string
        return os.getenv(self.default_kernel_name_env, os.getenv('KG_DEFAULT_KERNEL_NAME', ''))

    list_kernels_env = 'EG_LIST_KERNELS'
    list_kernels = Bool(config=True,
                        help="""Permits listing of the running kernels using API endpoints /api/kernels
                        and /api/sessions. (EG_LIST_KERNELS env var) Note: Jupyter Notebook
                        allows this by default but Jupyter Enterprise Gateway does not.""")

    @default('list_kernels')
    def list_kernels_default(self):
        return os.getenv(self.list_kernels_env, os.getenv('KG_LIST_KERNELS', 'False')).lower() == 'true'

    env_whitelist_env = 'EG_ENV_WHITELIST'
    env_whitelist = List(config=True,
                         help="""Environment variables allowed to be set when a client requests a
                         new kernel. (EG_ENV_WHITELIST env var)""")

    @default('env_whitelist')
    def env_whitelist_default(self):
        return os.getenv(self.env_whitelist_env, os.getenv('KG_ENV_WHITELIST', '')).split(',')

    env_process_whitelist_env = 'EG_ENV_PROCESS_WHITELIST'
    env_process_whitelist = List(config=True,
                                 help="""Environment variables allowed to be inherited
                                 from the spawning process by the kernel. (EG_ENV_PROCESS_WHITELIST env var)""")

    @default('env_process_whitelist')
    def env_process_whitelist_default(self):
        return os.getenv(self.env_process_whitelist_env, os.getenv('KG_ENV_PROCESS_WHITELIST', '')).split(',')

    # Remote hosts
    remote_hosts_env = 'EG_REMOTE_HOSTS'
    remote_hosts_default_value = 'localhost'
    remote_hosts = List(default_value=[remote_hosts_default_value], config=True,
                        help="""Bracketed comma-separated list of hosts on which DistributedProcessProxy
                        kernels will be launched e.g., ['host1','host2']. (EG_REMOTE_HOSTS env var
                        - non-bracketed, just comma-separated)""")

    @default('remote_hosts')
    def remote_hosts_default(self):
        return os.getenv(self.remote_hosts_env, self.remote_hosts_default_value).split(',')

    # Yarn endpoint
    yarn_endpoint_env = 'EG_YARN_ENDPOINT'
    yarn_endpoint = Unicode(None, config=True, allow_none=True,
                            help="""The http url specifying the YARN Resource Manager. Note: If this value is NOT set,
                            the YARN library will use the files within the local HADOOP_CONFIG_DIR to determine the
                            active resource manager. (EG_YARN_ENDPOINT env var)""")

    @default('yarn_endpoint')
    def yarn_endpoint_default(self):
        return os.getenv(self.yarn_endpoint_env)

    # Alt Yarn endpoint
    alt_yarn_endpoint_env = 'EG_ALT_YARN_ENDPOINT'
    alt_yarn_endpoint = Unicode(None, config=True, allow_none=True,
                                help="""The http url specifying the alternate YARN Resource Manager.  This value should
                                be set when YARN Resource Managers are configured for high availability.  Note: If both
                                YARN endpoints are NOT set, the YARN library will use the files within the local
                                HADOOP_CONFIG_DIR to determine the active resource manager.
                                (EG_ALT_YARN_ENDPOINT env var)""")

    @default('alt_yarn_endpoint')
    def alt_yarn_endpoint_default(self):
        return os.getenv(self.alt_yarn_endpoint_env)

    yarn_endpoint_security_enabled_env = 'EG_YARN_ENDPOINT_SECURITY_ENABLED'
    yarn_endpoint_security_enabled_default_value = False
    yarn_endpoint_security_enabled = Bool(yarn_endpoint_security_enabled_default_value, config=True,
                                          help="""Is YARN Kerberos/SPNEGO Security enabled (True/False).
                                          (EG_YARN_ENDPOINT_SECURITY_ENABLED env var)""")

    @default('yarn_endpoint_security_enabled')
    def yarn_endpoint_security_enabled_default(self):
        return bool(os.getenv(self.yarn_endpoint_security_enabled_env,
                              self.yarn_endpoint_security_enabled_default_value))

    # Conductor endpoint
    conductor_endpoint_env = 'EG_CONDUCTOR_ENDPOINT'
    conductor_endpoint_default_value = None
    conductor_endpoint = Unicode(conductor_endpoint_default_value, config=True,
                                 help="""The http url for accessing the Conductor REST API.
                                 (EG_CONDUCTOR_ENDPOINT env var)""")

    @default('conductor_endpoint')
    def conductor_endpoint_default(self):
        return os.getenv(self.conductor_endpoint_env, self.conductor_endpoint_default_value)

    _log_formatter_cls = LogFormatter  # traitlet default is LevelFormatter

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
                             help="""Comma-separated list of user names (e.g., ['root','admin']) against which
                             KERNEL_USERNAME will be compared.  Any match (case-sensitive) will prevent the
                             kernel's launch and result in an HTTP 403 (Forbidden) error.
                             (EG_UNAUTHORIZED_USERS env var - non-bracketed, just comma-separated)""")

    @default('unauthorized_users')
    def unauthorized_users_default(self):
        return os.getenv(self.unauthorized_users_env, self.unauthorized_users_default_value).split(',')

    # Authorized users
    authorized_users_env = 'EG_AUTHORIZED_USERS'
    authorized_users = Set(config=True,
                           help="""Comma-separated list of user names (e.g., ['bob','alice']) against which
                           KERNEL_USERNAME will be compared.  Any match (case-sensitive) will allow the kernel's
                           launch, otherwise an HTTP 403 (Forbidden) error will be raised.  The set of unauthorized
                           users takes precedence. This option should be used carefully as it can dramatically limit
                           who can launch kernels.  (EG_AUTHORIZED_USERS env var - non-bracketed,
                           just comma-separated)""")

    @default('authorized_users')
    def authorized_users_default(self):
        au_env = os.getenv(self.authorized_users_env)
        return au_env.split(',') if au_env is not None else []

    # Port range
    port_range_env = 'EG_PORT_RANGE'
    port_range_default_value = "0..0"
    port_range = Unicode(port_range_default_value, config=True,
                         help="""Specifies the lower and upper port numbers from which ports are created.
                         The bounded values are separated by '..' (e.g., 33245..34245 specifies a range of 1000 ports
                         to be randomly selected). A range of zero (e.g., 33245..33245 or 0..0) disables port-range
                         enforcement.  (EG_PORT_RANGE env var)""")

    @default('port_range')
    def port_range_default(self):
        return os.getenv(self.port_range_env, self.port_range_default_value)

    # Max Kernels per User
    max_kernels_per_user_env = 'EG_MAX_KERNELS_PER_USER'
    max_kernels_per_user_default_value = -1
    max_kernels_per_user = Integer(max_kernels_per_user_default_value, config=True,
                                   help="""Specifies the maximum number of kernels a user can have active
                                   simultaneously.  A value of -1 disables enforcement.
                                   (EG_MAX_KERNELS_PER_USER env var)""")

    @default('max_kernels_per_user')
    def max_kernels_per_user_default(self):
        return int(os.getenv(self.max_kernels_per_user_env, self.max_kernels_per_user_default_value))

    ws_ping_interval_env = 'EG_WS_PING_INTERVAL_SECS'
    ws_ping_interval_default_value = 30
    ws_ping_interval = Integer(ws_ping_interval_default_value, config=True,
                               help="""Specifies the ping interval(in seconds) that should be used by zmq port
                                     associated withspawned kernels.Set this variable to 0 to disable ping mechanism.
                                    (EG_WS_PING_INTERVAL_SECS env var)""")

    @default('ws_ping_interval')
    def ws_ping_interval_default(self):
        return int(os.getenv(self.ws_ping_interval_env, self.ws_ping_interval_default_value))

    # Dynamic Update Interval
    dynamic_config_interval_env = 'EG_DYNAMIC_CONFIG_INTERVAL'
    dynamic_config_interval_default_value = 0
    dynamic_config_interval = Integer(dynamic_config_interval_default_value, min=0, config=True,
                                      help="""Specifies the number of seconds configuration files are polled for
                                      changes.  A value of 0 or less disables dynamic config updates.
                                      (EG_DYNAMIC_CONFIG_INTERVAL env var)""")

    @default('dynamic_config_interval')
    def dynamic_config_interval_default(self):
        return int(os.getenv(self.dynamic_config_interval_env, self.dynamic_config_interval_default_value))

    @observe('dynamic_config_interval')
    def dynamic_config_interval_changed(self, event):
        prev_val = event['old']
        self.dynamic_config_interval = event['new']
        if self.dynamic_config_interval != prev_val:
            # Values are different.  Stop the current poller.  If new value is > 0, start a poller.
            if self.dynamic_config_poller:
                self.dynamic_config_poller.stop()
                self.dynamic_config_poller = None

            if self.dynamic_config_interval <= 0:
                self.log.warning("Dynamic configuration updates have been disabled and cannot be re-enabled "
                                 "without restarting Enterprise Gateway!")
            elif prev_val > 0:  # The interval has been changed, but still positive
                self.init_dynamic_configs()  # Restart the poller

    dynamic_config_poller = None

    kernel_spec_manager = Instance(KernelSpecManager, allow_none=True)

    kernel_spec_manager_class = Type(
        default_value=KernelSpecManager,
        config=True,
        help="""
        The kernel spec manager class to use. Must be a subclass
        of `jupyter_client.kernelspec.KernelSpecManager`.
        """
    )

    kernel_manager_class = Type(
        klass=MappingKernelManager,
        default_value=RemoteMappingKernelManager,
        config=True,
        help="""
        The kernel manager class to use. Must be a subclass
        of `notebook.services.kernels.MappingKernelManager`.
        """
    )

    kernel_session_manager_class = Type(
        klass=KernelSessionManager,
        default_value=FileKernelSessionManager,
        config=True,
        help="""
        The kernel session manager class to use. Must be a subclass
        of `enterprise_gateway.services.sessions.KernelSessionManager`.
        """
    )

    def initialize(self, argv=None):
        """Initializes the base class, configurable manager instances, the
        Tornado web app, and the tornado HTTP server.

        Parameters
        ----------
        argv
            Command line arguments
        """
        super(EnterpriseGatewayApp, self).initialize(argv)
        self.init_configurables()
        self.init_webapp()
        self.init_http_server()

    def init_configurables(self):
        """Initializes all configurable objects including a kernel manager, kernel
        spec manager, session manager, and personality.
        """
        self.kernel_spec_manager = KernelSpecManager(parent=self)

        # Only pass a default kernel name when one is provided. Otherwise,
        # adopt whatever default the kernel manager wants to use.
        kwargs = {}
        if self.default_kernel_name:
            kwargs['default_kernel_name'] = self.default_kernel_name

        self.kernel_spec_manager = self.kernel_spec_manager_class(
            parent=self,
        )

        self.kernel_manager = self.kernel_manager_class(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs
        )

        self.session_manager = SessionManager(
            log=self.log,
            kernel_manager=self.kernel_manager
        )

        self.kernel_session_manager = self.kernel_session_manager_class(
            parent=self,
            log=self.log,
            kernel_manager=self.kernel_manager,
            config=self.config,  # required to get command-line options visible
            **kwargs
        )

        # Attempt to start persisted sessions
        # Commented as part of https://github.com/jupyter/enterprise_gateway/pull/737#issuecomment-567598751
        # self.kernel_session_manager.start_sessions()

        self.contents_manager = None  # Gateways don't use contents manager

        self.init_dynamic_configs()

    def _create_request_handlers(self):
        """Create default Jupyter handlers and redefine them off of the
        base_url path. Assumes init_configurables() has already been called.
        """
        handlers = []

        # append tuples for the standard kernel gateway endpoints
        for handler in (
            default_api_handlers +
            default_kernel_handlers +
            default_kernelspec_handlers +
            default_session_handlers +
            default_base_handlers
        ):
            # Create a new handler pattern rooted at the base_url
            pattern = url_path_join('/', self.base_url, handler[0])
            # Some handlers take args, so retain those in addition to the
            # handler class ref
            new_handler = tuple([pattern] + list(handler[1:]))
            handlers.append(new_handler)
        return handlers

    def init_webapp(self):
        """Initializes Tornado web application with uri handlers.

        Adds the various managers and web-front configuration values to the
        Tornado settings for reference by the handlers.
        """
        # Enable the same pretty logging the notebook uses
        enable_pretty_logging()

        # Configure the tornado logging level too
        logging.getLogger().setLevel(self.log_level)

        handlers = self._create_request_handlers()

        self.web_app = web.Application(
            handlers=handlers,
            kernel_manager=self.kernel_manager,
            session_manager=self.session_manager,
            contents_manager=self.contents_manager,
            kernel_spec_manager=self.kernel_spec_manager,
            eg_auth_token=self.auth_token,
            eg_allow_credentials=self.allow_credentials,
            eg_allow_headers=self.allow_headers,
            eg_allow_methods=self.allow_methods,
            eg_allow_origin=self.allow_origin,
            eg_expose_headers=self.expose_headers,
            eg_max_age=self.max_age,
            eg_max_kernels=self.max_kernels,
            eg_env_process_whitelist=self.env_process_whitelist,
            eg_env_whitelist=self.env_whitelist,
            eg_list_kernels=self.list_kernels,
            # Also set the allow_origin setting used by notebook so that the
            # check_origin method used everywhere respects the value
            allow_origin=self.allow_origin,
            # Always allow remote access (has been limited to localhost >= notebook 5.6)
            allow_remote_access=True,
            # setting ws_ping_interval value that can allow it to be modified for the purpose of toggling ping mechanism
            # for zmq web-sockets or increasing/decreasing web socket ping interval/timeouts.
            ws_ping_interval=self.ws_ping_interval * 1000
        )

    def _build_ssl_options(self):
        """Build a dictionary of SSL options for the tornado HTTP server.

        Taken directly from jupyter/notebook code.
        """
        ssl_options = {}
        if self.certfile:
            ssl_options['certfile'] = self.certfile
        if self.keyfile:
            ssl_options['keyfile'] = self.keyfile
        if self.client_ca:
            ssl_options['ca_certs'] = self.client_ca
        if not ssl_options:
            # None indicates no SSL config
            ssl_options = None
        else:
            # SSL may be missing, so only import it if it's to be used
            import ssl
            # PROTOCOL_TLS selects the highest ssl/tls protocol version that both the client and
            # server support. When PROTOCOL_TLS is not available use PROTOCOL_SSLv23.
            # PROTOCOL_TLS is new in version 2.7.13, 3.5.3 and 3.6
            ssl_options.setdefault(
                'ssl_version',
                getattr(ssl, 'PROTOCOL_TLS', ssl.PROTOCOL_SSLv23)
            )
            if ssl_options.get('ca_certs', False):
                ssl_options.setdefault('cert_reqs', ssl.CERT_REQUIRED)

        return ssl_options

    def init_http_server(self):
        """Initializes a HTTP server for the Tornado web application on the
        configured interface and port.

        Tries to find an open port if the one configured is not available using
        the same logic as the Jupyer Notebook server.
        """
        ssl_options = self._build_ssl_options()
        self.http_server = httpserver.HTTPServer(self.web_app,
                                                 xheaders=self.trust_xheaders,
                                                 ssl_options=ssl_options)

        for port in random_ports(self.port, self.port_retries + 1):
            try:
                self.http_server.listen(port, self.ip)
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:
                    self.log.info('The port %i is already in use, trying another port.' % port)
                    continue
                elif e.errno in (errno.EACCES, getattr(errno, 'WSAEACCES', errno.EACCES)):
                    self.log.warning("Permission to listen on port %i denied" % port)
                    continue
                else:
                    raise
            else:
                self.port = port
                break
        else:
            self.log.critical('ERROR: the gateway server could not be started because '
                              'no available port could be found.')
            self.exit(1)

    def start(self):
        """Starts an IO loop for the application. """

        super(EnterpriseGatewayApp, self).start()

        self.log.info('Jupyter Enterprise Gateway {} is available at http{}://{}:{}'.format(
            EnterpriseGatewayApp.version, 's' if self.keyfile else '', self.ip, self.port
        ))
        # If impersonation is enabled, issue a warning message if the gateway user is not in unauthorized_users.
        if self.impersonation_enabled:
            gateway_user = getpass.getuser()
            if gateway_user.lower() not in self.unauthorized_users:
                self.log.warning("Impersonation is enabled and gateway user '{}' is NOT specified in the set of "
                                 "unauthorized users!  Kernels may execute as that user with elevated privileges.".
                                 format(gateway_user))

        self.io_loop = ioloop.IOLoop.current()

        if sys.platform != 'win32':
            signal.signal(signal.SIGHUP, signal.SIG_IGN)

        signal.signal(signal.SIGTERM, self._signal_stop)

        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.log.info("Interrupted...")
            # Ignore further interrupts (ctrl-c)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        finally:
            self.shutdown()

    def shutdown(self):
        """Shuts down all running kernels."""
        kids = self.kernel_manager.list_kernel_ids()
        for kid in kids:
            self.kernel_manager.shutdown_kernel(kid, now=True)

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
        self.io_loop.add_callback_from_signal(self.io_loop.stop)

    _last_config_update = int(time.time())
    _dynamic_configurables = {}

    def update_dynamic_configurables(self):
        """
        Called periodically, this checks the set of loaded configuration files for updates.
        If updates have been detected, reload the configuration files and update the list of
        configurables participating in dynamic updates.
        :return: True if updates were taken
        """
        updated = False
        configs = []
        for file in self.loaded_config_files:
            mod_time = int(os.path.getmtime(file))
            if mod_time > self._last_config_update:
                self.log.debug("Config file was updated: {}!".format(file))
                self._last_config_update = mod_time
                updated = True

        if updated:
            # If config changes are present, reload the config files.  This will also update
            # the Application's configuration, then update the config of each configurable
            # from the newly loaded values.

            self.load_config_file(self)

            for config_name, configurable in self._dynamic_configurables.items():
                # Since Application.load_config_file calls update_config on the Application, skip
                # the configurable registered with self (i.e., the application).
                if configurable is not self:
                    configurable.update_config(self.config)
                configs.append(config_name)

            self.log.info("Configuration file changes detected.  Instances for the following "
                          "configurables have been updated: {}".format(configs))
        return updated

    def add_dynamic_configurable(self, config_name, configurable):
        """
        Adds the configurable instance associated with the given name to the list of Configurables
        that can have their configurations updated when configuration file updates are detected.
        :param config_name: the name of the config within this application
        :param configurable: the configurable instance corresponding to that config
        """
        if not isinstance(configurable, Configurable):
            raise RuntimeError("'{}' is not a subclass of Configurable!".format(configurable))

        self._dynamic_configurables[config_name] = weakref.proxy(configurable)

    def init_dynamic_configs(self):
        """
        Initialize the set of configurables that should participate in dynamic updates.  We should
        also log that we're performing dynamic configuration updates, along with the list of CLI
        options - that are not privy to dynamic updates.
        :return:
        """
        if self.dynamic_config_interval > 0:
            self.add_dynamic_configurable('EnterpriseGatewayApp', self)
            self.add_dynamic_configurable('MappingKernelManager', self.kernel_manager)
            self.add_dynamic_configurable('KernelSpecManager', self.kernel_spec_manager)
            self.add_dynamic_configurable('KernelSessionManager', self.kernel_session_manager)

            self.log.info("Dynamic updates have been configured.  Checking every {} seconds.".
                          format(self.dynamic_config_interval))

            self.log.info("The following configuration options will not be subject to dynamic updates "
                          "(configured via CLI):")
            for config, options in self.cli_config.items():
                for option, value in options.items():
                    self.log.info("    '{}.{}': '{}'".format(config, option, value))

            if self.dynamic_config_poller is None:
                self.dynamic_config_poller = ioloop.PeriodicCallback(self.update_dynamic_configurables,
                                                                     self.dynamic_config_interval * 1000)
            self.dynamic_config_poller.start()


launch_instance = EnterpriseGatewayApp.launch_instance
