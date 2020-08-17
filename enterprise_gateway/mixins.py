# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Mixins for Tornado handlers."""

from distutils.util import strtobool
from http.client import responses
import json
import os
import ssl
import traceback

from tornado import web
from tornado.log import LogFormatter

from traitlets import default, List, Set, Unicode, Type, Instance, Bool, CBool, Integer, observe
from traitlets.config import Configurable


class CORSMixin(object):
    """Mixes CORS headers into tornado.web.RequestHandlers."""
    SETTINGS_TO_HEADERS = {
        'eg_allow_credentials': 'Access-Control-Allow-Credentials',
        'eg_allow_headers': 'Access-Control-Allow-Headers',
        'eg_allow_methods': 'Access-Control-Allow-Methods',
        'eg_allow_origin': 'Access-Control-Allow-Origin',
        'eg_expose_headers': 'Access-Control-Expose-Headers',
        'eg_max_age': 'Access-Control-Max-Age'
    }

    def set_default_headers(self):
        """Sets the CORS headers as the default for all responses.

        Disables CSP configured by the notebook package. It's not necessary
        for a programmatic API.
        """
        super(CORSMixin, self).set_default_headers()
        # Add CORS headers after default if they have a non-blank value
        for settings_name, header_name in self.SETTINGS_TO_HEADERS.items():
            header_value = self.settings.get(settings_name)
            if header_value:
                self.set_header(header_name, header_value)

        # Don't set CSP: we're not serving frontend media types, only JSON
        self.clear_header('Content-Security-Policy')

    def options(self):
        """Override the notebook implementation to return the headers
        configured in `set_default_headers instead of the hardcoded set
        supported by the handler base class in the notebook project.
        """
        self.finish()


class TokenAuthorizationMixin(object):
    """Mixes token auth into tornado.web.RequestHandlers and
    tornado.websocket.WebsocketHandlers.
    """
    header_prefix = "token "
    header_prefix_len = len(header_prefix)

    def prepare(self):
        """Ensures the correct auth token is present, either as a parameter
        `token=<value>` or as a header `Authorization: token <value>`.
        Does nothing unless an auth token is configured in eg_auth_token.

        If eg_auth_token is set and the token is not present, responds
        with 401 Unauthorized.

        Notes
        -----
        Implemented in prepare rather than in `get_user` to avoid interaction
        with the `@web.authenticated` decorated methods in the notebook
        package.
        """
        server_token = self.settings.get('eg_auth_token')
        if server_token and not self.request.method == 'OPTIONS':
            client_token = self.get_argument('token', None)
            if client_token is None:
                client_token = self.request.headers.get('Authorization')
                if client_token and client_token.startswith(self.header_prefix):
                    client_token = client_token[self.header_prefix_len:]
                else:
                    client_token = None
            if client_token != server_token:
                return self.send_error(401)
        return super(TokenAuthorizationMixin, self).prepare()


class JSONErrorsMixin(object):
    """Mixes `write_error` into tornado.web.RequestHandlers to respond with
    JSON format errors.
    """
    def write_error(self, status_code, **kwargs):
        """Responds with an application/json error object.

        Overrides the APIHandler.write_error in the notebook server until it
        properly sets the 'reason' field.

        Parameters
        ----------
        status_code
            HTTP status code to set
        **kwargs
            Arbitrary keyword args. Only uses `exc_info[1]`, if it exists,
            to get a `log_message`, `args`, and `reason` from a raised
            exception that triggered this method

        Examples
        --------
        {"401", reason="Unauthorized", message="Invalid auth token"}
        """
        exc_info = kwargs.get('exc_info')
        message = ''
        reason = responses.get(status_code, 'Unknown HTTP Error')
        reply = {
            'reason': reason,
            'message': message,
        }
        if exc_info:
            exception = exc_info[1]
            # Get the custom message, if defined
            if isinstance(exception, web.HTTPError):
                reply['message'] = exception.log_message or message
            else:
                reply['message'] = 'Unknown server error'
                reply['traceback'] = ''.join(traceback.format_exception(*exc_info))

            # Construct the custom reason, if defined
            custom_reason = getattr(exception, 'reason', '')
            if custom_reason:
                reply['reason'] = custom_reason

        self.set_header('Content-Type', 'application/json')
        self.set_status(status_code, reason=reply['reason'])
        self.finish(json.dumps(reply))


class EnterpriseGatewayConfigMixin(Configurable):
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

    ssl_version_env = 'EG_SSL_VERSION'
    ssl_version_default_value = ssl.PROTOCOL_TLSv1_2
    ssl_version = Integer(None, config=True, allow_none=True,
                          help="""Sets the SSL version to use for the web socket
                          connection. (EG_SSL_VERSION env var)""")

    @default('ssl_version')
    def ssl_version_default(self):
        ssl_from_env = os.getenv(self.ssl_version_env, os.getenv('KG_SSL_VERSION'))
        return ssl_from_env if ssl_from_env is None else int(ssl_from_env)

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
    conductor_endpoint = Unicode(conductor_endpoint_default_value,
                                 allow_none=True,
                                 config=True,
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
            # The interval has been changed, but still positive
            elif prev_val > 0 and hasattr(self, "init_dynamic_configs"):
                self.init_dynamic_configs()  # Restart the poller

    dynamic_config_poller = None

    kernel_spec_manager = Instance("jupyter_client.kernelspec.KernelSpecManager", allow_none=True)

    kernel_spec_manager_class = Type(
        default_value="jupyter_client.kernelspec.KernelSpecManager",
        config=True,
        help="""
        The kernel spec manager class to use. Must be a subclass
        of `jupyter_client.kernelspec.KernelSpecManager`.
        """
    )

    kernel_manager_class = Type(
        klass="enterprise_gateway.services.kernels.remotemanager.RemoteMappingKernelManager",
        default_value="enterprise_gateway.services.kernels.remotemanager.RemoteMappingKernelManager",
        config=True,
        help="""
        The kernel manager class to use. Must be a subclass
        of `enterprise_gateway.services.kernels.RemoteMappingKernelManager`.
        """
    )

    kernel_session_manager_class = Type(
        klass="enterprise_gateway.services.sessions.kernelsessionmanager.KernelSessionManager",
        default_value="enterprise_gateway.services.sessions.kernelsessionmanager.FileKernelSessionManager",
        config=True,
        help="""
        The kernel session manager class to use. Must be a subclass
        of `enterprise_gateway.services.sessions.KernelSessionManager`.
        """
    )
