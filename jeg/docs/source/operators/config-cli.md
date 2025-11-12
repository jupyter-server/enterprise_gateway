# Command-line options

In some cases, it may be easier to use command line options. These can also be used for _static_ values that should not be the targeted for [_dynamic configurables_](config-dynamic.md/#dynamic-configurables).

To see the same configuration options at the command line, run the following:

```bash
jupyter enterprisegateway --help-all
```

A snapshot of this help appears below for ease of reference. The options for the superclass `EnterpriseGatewayConfigMixin` have been omitted. As with the `--generate-config` option, each option includes its corresponding environment variable, if applicable.

```text
Jupyter Enterprise Gateway

Provisions remote Jupyter kernels and proxies HTTP/Websocket traffic to them.

Options
-------

Arguments that take values are actually convenience aliases to full
Configurables, whose aliases are listed on the help line. For more information
on full configurables, see '--help-all'.

--debug
    set log level to logging.DEBUG (maximize logging output)
--generate-config
    generate default config file
-y
    Answer yes to any questions instead of prompting.
--log-level=<Enum> (Application.log_level)
    Default: 30
    Choices: (0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    Set the log level by value or name.
--config=<Unicode> (JupyterApp.config_file)
    Default: ''
    Full path of a config file.
--ip=<Unicode> (EnterpriseGatewayApp.ip)
    Default: '127.0.0.1'
    IP address on which to listen (EG_IP env var)
--port=<Int> (EnterpriseGatewayApp.port)
    Default: 8888
    Port on which to listen (EG_PORT env var)
--port_retries=<Int> (EnterpriseGatewayApp.port_retries)
    Default: 50
    Number of ports to try if the specified port is not available
    (EG_PORT_RETRIES env var)
--keyfile=<Unicode> (EnterpriseGatewayApp.keyfile)
    Default: None
    The full path to a private key file for usage with SSL/TLS. (EG_KEYFILE env
    var)
--certfile=<Unicode> (EnterpriseGatewayApp.certfile)
    Default: None
    The full path to an SSL/TLS certificate file. (EG_CERTFILE env var)
--client-ca=<Unicode> (EnterpriseGatewayApp.client_ca)
    Default: None
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (EG_CLIENT_CA env var)

Class parameters
----------------

Parameters are set from command-line arguments of the form:
`--Class.trait=value`. This line is evaluated in Python, so simple expressions
are allowed, e.g.:: `--C.a='range(3)'` For setting C.a=[0,1,2].

EnterpriseGatewayApp(EnterpriseGatewayConfigMixin, JupyterApp) options
----------------------------------------------------------------------
--EnterpriseGatewayApp.allow_credentials=<Unicode>
    Sets the Access-Control-Allow-Credentials header. (EG_ALLOW_CREDENTIALS env
    var)
    Default: ''
--EnterpriseGatewayApp.allow_headers=<Unicode>
    Sets the Access-Control-Allow-Headers header. (EG_ALLOW_HEADERS env var)
    Default: ''
--EnterpriseGatewayApp.allow_methods=<Unicode>
    Sets the Access-Control-Allow-Methods header. (EG_ALLOW_METHODS env var)
    Default: ''
--EnterpriseGatewayApp.allow_origin=<Unicode>
    Sets the Access-Control-Allow-Origin header. (EG_ALLOW_ORIGIN env var)
    Default: ''
--EnterpriseGatewayApp.alt_yarn_endpoint=<Unicode>
    The http url specifying the alternate YARN Resource Manager.  This value
    should be set when YARN Resource Managers are configured for high
    availability.  Note: If both YARN endpoints are NOT set, the YARN library
    will use the files within the local HADOOP_CONFIG_DIR to determine the
    active resource manager. (EG_ALT_YARN_ENDPOINT env var)
    Default: None
--EnterpriseGatewayApp.answer_yes=<Bool>
    Answer yes to any prompts.
    Default: False
--EnterpriseGatewayApp.auth_token=<Unicode>
    Authorization token required for all requests (EG_AUTH_TOKEN env var)
    Default: ''
--EnterpriseGatewayApp.authorized_users=<set-item-1>...
    Comma-separated list of user names (e.g., ['bob','alice']) against which
    KERNEL_USERNAME will be compared.  Any match (case-sensitive) will allow the
    kernel's launch, otherwise an HTTP 403 (Forbidden) error will be raised.
    The set of unauthorized users takes precedence. This option should be used
    carefully as it can dramatically limit who can launch kernels.
    (EG_AUTHORIZED_USERS env var - non-bracketed, just comma-separated)
    Default: set()
--EnterpriseGatewayApp.authorized_origin=<Unicode>
    Hostname (e.g. 'localhost', 'reverse.proxy.net') which the handler will
    match against the request's SSL certificate.  An HTTP 403 (Forbidden) error
    will be raised on a failed match.  This option requires TLS to be enabled.
    It does not support IP addresses. (EG_AUTHORIZED_ORIGIN env var)
    Default: ''
--EnterpriseGatewayApp.availability_mode=<CaselessStrEnum>
    Specifies the type of availability.  Values must be one of "standalone"
    or "replication".  (EG_AVAILABILITY_MODE env var)
    Choices: any of ['standalone', 'replication'] (case-insensitive) or None
    Default: None
--EnterpriseGatewayApp.base_url=<Unicode>
    The base path for mounting all API resources (EG_BASE_URL env var)
    Default: '/'
--EnterpriseGatewayApp.certfile=<Unicode>
    The full path to an SSL/TLS certificate file. (EG_CERTFILE env var)
    Default: None
--EnterpriseGatewayApp.client_ca=<Unicode>
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (EG_CLIENT_CA env var)
    Default: None
--EnterpriseGatewayApp.client_envs=<list-item-1>...
    Environment variables allowed to be set when a client requests a
    new kernel. (EG_CLIENT_ENVS env var)
    Default: []
--EnterpriseGatewayApp.conductor_endpoint=<Unicode>
    The http url for accessing the Conductor REST API. (EG_CONDUCTOR_ENDPOINT
    env var)
    Default: None
--EnterpriseGatewayApp.config_file=<Unicode>
    Full path of a config file.
    Default: ''
--EnterpriseGatewayApp.config_file_name=<Unicode>
    Specify a config file to load.
    Default: ''
--EnterpriseGatewayApp.default_kernel_name=<Unicode>
    Default kernel name when spawning a kernel (EG_DEFAULT_KERNEL_NAME env var)
    Default: ''
--EnterpriseGatewayApp.dynamic_config_interval=<Int>
    Specifies the number of seconds configuration files are polled for changes.
    A value of 0 or less disables dynamic config updates.
    (EG_DYNAMIC_CONFIG_INTERVAL env var)
    Default: 0
--EnterpriseGatewayApp.env_process_whitelist=<list-item-1>...
    DEPRECATED, use inherited_envs
    Default: []
--EnterpriseGatewayApp.env_whitelist=<list-item-1>...
    DEPRECATED, use client_envs.
    Default: []
--EnterpriseGatewayApp.expose_headers=<Unicode>
    Sets the Access-Control-Expose-Headers header. (EG_EXPOSE_HEADERS env var)
    Default: ''
--EnterpriseGatewayApp.generate_config=<Bool>
    Generate default config file.
    Default: False
--EnterpriseGatewayApp.impersonation_enabled=<Bool>
    Indicates whether impersonation will be performed during kernel launch.
    (EG_IMPERSONATION_ENABLED env var)
    Default: False
--EnterpriseGatewayApp.inherited_envs=<list-item-1>...
    Environment variables allowed to be inherited
    from the spawning process by the kernel. (EG_INHERITED_ENVS env var)
    Default: []
--EnterpriseGatewayApp.ip=<Unicode>
    IP address on which to listen (EG_IP env var)
    Default: '127.0.0.1'
--EnterpriseGatewayApp.kernel_headers=<list-item-1>...
    Request headers to make available to kernel launch framework.
    (EG_KERNEL_HEADERS env var)
    Default: []
--EnterpriseGatewayApp.kernel_manager_class=<Type>
    The kernel manager class to use. Must be a subclass of
    `enterprise_gateway.services.kernels.RemoteMappingKernelManager`.
    Default: 'enterprise_gateway.services.kernels.remotemanager.RemoteMapp...
--EnterpriseGatewayApp.kernel_session_manager_class=<Type>
    The kernel session manager class to use. Must be a subclass of
    `enterprise_gateway.services.sessions.KernelSessionManager`.
    Default: 'enterprise_gateway.services.sessions.kernelsessionmanager.Fi...
--EnterpriseGatewayApp.kernel_spec_cache_class=<Type>
    The kernel spec cache class to use. Must be a subclass of
    `enterprise_gateway.services.kernelspecs.KernelSpecCache`.
    Default: 'enterprise_gateway.services.kernelspecs.kernelspec_cache.Ker...
--EnterpriseGatewayApp.kernel_spec_manager_class=<Type>
    The kernel spec manager class to use. Must be a subclass of
    `jupyter_client.kernelspec.KernelSpecManager`.
    Default: 'jupyter_client.kernelspec.KernelSpecManager'
--EnterpriseGatewayApp.keyfile=<Unicode>
    The full path to a private key file for usage with SSL/TLS. (EG_KEYFILE env
    var)
    Default: None
--EnterpriseGatewayApp.list_kernels=<Bool>
    Permits listing of the running kernels using API endpoints /api/kernels and
    /api/sessions. (EG_LIST_KERNELS env var) Note: Jupyter Notebook allows this
    by default but Jupyter Enterprise Gateway does not.
    Default: False
--EnterpriseGatewayApp.load_balancing_algorithm=<Unicode>
    Specifies which load balancing algorithm DistributedProcessProxy should use.
    Must be one of "round-robin" or "least-connection".
    (EG_LOAD_BALANCING_ALGORITHM env var)
    Default: 'round-robin'
--EnterpriseGatewayApp.log_datefmt=<Unicode>
    The date format used by logging formatters for %(asctime)s
    Default: '%Y-%m-%d %H:%M:%S'
--EnterpriseGatewayApp.log_format=<Unicode>
    The Logging format template
    Default: '[%(name)s]%(highlevel)s %(message)s'
--EnterpriseGatewayApp.log_level=<Enum>
    Set the log level by value or name.
    Choices: any of [0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
    Default: 30
--EnterpriseGatewayApp.max_age=<Unicode>
    Sets the Access-Control-Max-Age header. (EG_MAX_AGE env var)
    Default: ''
--EnterpriseGatewayApp.max_kernels=<Int>
    Limits the number of kernel instances allowed to run by this gateway.
    Unbounded by default. (EG_MAX_KERNELS env var)
    Default: None
--EnterpriseGatewayApp.max_kernels_per_user=<Int>
    Specifies the maximum number of kernels a user can have active
    simultaneously.  A value of -1 disables enforcement.
    (EG_MAX_KERNELS_PER_USER env var)
    Default: -1
--EnterpriseGatewayApp.port=<Int>
    Port on which to listen (EG_PORT env var)
    Default: 8888
--EnterpriseGatewayApp.port_range=<Unicode>
    Specifies the lower and upper port numbers from which ports are created. The
    bounded values are separated by '..' (e.g., 33245..34245 specifies a range
    of 1000 ports to be randomly selected). A range of zero (e.g., 33245..33245
    or 0..0) disables port-range enforcement.  (EG_PORT_RANGE env var)
    Default: '0..0'
--EnterpriseGatewayApp.port_retries=<Int>
    Number of ports to try if the specified port is not available
    (EG_PORT_RETRIES env var)
    Default: 50
--EnterpriseGatewayApp.remote_hosts=<list-item-1>...
    Bracketed comma-separated list of hosts on which DistributedProcessProxy
    kernels will be launched e.g., ['host1','host2']. (EG_REMOTE_HOSTS env var -
    non-bracketed, just comma-separated)
    Default: ['localhost']
--EnterpriseGatewayApp.show_config=<Bool>
    Instead of starting the Application, dump configuration to stdout
    Default: False
--EnterpriseGatewayApp.show_config_json=<Bool>
    Instead of starting the Application, dump configuration to stdout (as JSON)
    Default: False
--EnterpriseGatewayApp.ssl_version=<Int>
    Sets the SSL version to use for the web socket connection. (EG_SSL_VERSION
    env var)
    Default: None
--EnterpriseGatewayApp.trust_xheaders=<CBool>
    Use x-* header values for overriding the remote-ip, useful when application
    is behind a proxy. (EG_TRUST_XHEADERS env var)
    Default: False
--EnterpriseGatewayApp.unauthorized_users=<set-item-1>...
    Comma-separated list of user names (e.g., ['root','admin']) against which
    KERNEL_USERNAME will be compared.  Any match (case-sensitive) will prevent
    the kernel's launch and result in an HTTP 403 (Forbidden) error.
    (EG_UNAUTHORIZED_USERS env var - non-bracketed, just comma-separated)
    Default: {'root'}
--EnterpriseGatewayApp.ws_ping_interval=<Int>
    Specifies the ping interval(in seconds) that should be used by zmq port
     associated with spawned kernels.Set this variable to 0 to disable ping mechanism.
    (EG_WS_PING_INTERVAL_SECS env var)
    Default: 30
--EnterpriseGatewayApp.yarn_endpoint=<Unicode>
    The http url specifying the YARN Resource Manager. Note: If this value is
    NOT set, the YARN library will use the files within the local
    HADOOP_CONFIG_DIR to determine the active resource manager.
    (EG_YARN_ENDPOINT env var)
    Default: None
--EnterpriseGatewayApp.yarn_endpoint_security_enabled=<Bool>
    Is YARN Kerberos/SPNEGO Security enabled (True/False).
    (EG_YARN_ENDPOINT_SECURITY_ENABLED env var)
    Default: False

KernelSpecCache(SingletonConfigurable) options
----------------------------------------------
--KernelSpecCache.cache_enabled=<CBool>
    Enable Kernel Specification caching. (EG_KERNELSPEC_CACHE_ENABLED env var)
    Default: False

FileKernelSessionManager(KernelSessionManager) options
------------------------------------------------------
--FileKernelSessionManager.enable_persistence=<Bool>
    Enable kernel session persistence (True or False). Default = False
    (EG_KERNEL_SESSION_PERSISTENCE env var)
    Default: False
--FileKernelSessionManager.persistence_root=<Unicode>
    Identifies the root 'directory' under which the 'kernel_sessions' node will
    reside.  This directory should exist.  (EG_PERSISTENCE_ROOT env var)
    Default: ''

WebhookKernelSessionManager(KernelSessionManager) options
---------------------------------------------------------
--WebhookKernelSessionManager.enable_persistence=<Bool>
    Enable kernel session persistence (True or False). Default = False
    (EG_KERNEL_SESSION_PERSISTENCE env var)
    Default: False
--WebhookKernelSessionManager.persistence_root=<Unicode>
    Identifies the root 'directory' under which the 'kernel_sessions' node will
    reside.  This directory should exist.  (EG_PERSISTENCE_ROOT env var)
    Default: None
--WebhookKernelSessionManager.webhook_url=<Unicode>
    URL endpoint for webhook kernel session manager
    Default: None
--WebhookKernelSessionManager.auth_type=<Unicode>
    Authentication type for webhook kernel session manager API. Either basic, digest or None
    Default: None
--WebhookKernelSessionManager.webhook_username=<Unicode>
    Username for webhook kernel session manager API auth
    Default: None
--WebhookKernelSessionManager.webhook_password=<Unicode>
    Password for webhook kernel session manager API auth
    Default: None

RemoteMappingKernelManager(AsyncMappingKernelManager) options
-------------------------------------------------------------
--RemoteMappingKernelManager.allowed_message_types=<list-item-1>...
    White list of allowed kernel message types. When the list is empty, all
    message types are allowed.
    Default: []
--RemoteMappingKernelManager.buffer_offline_messages=<Bool>
    Whether messages from kernels whose frontends have disconnected should be
    buffered in-memory. When True (default), messages are buffered and replayed
    on reconnect, avoiding lost messages due to interrupted connectivity.
    Disable if long-running kernels will produce too much output while no
    frontends are connected.
    Default: True
--RemoteMappingKernelManager.cull_busy=<Bool>
    Whether to consider culling kernels which are busy. Only effective if
    cull_idle_timeout > 0.
    Default: False
--RemoteMappingKernelManager.cull_connected=<Bool>
    Whether to consider culling kernels which have one or more connections. Only
    effective if cull_idle_timeout > 0.
    Default: False
--RemoteMappingKernelManager.cull_idle_timeout=<Int>
    Timeout (in seconds) after which a kernel is considered idle and ready to be
    culled. Values of 0 or lower disable culling. Very short timeouts may result
    in kernels being culled for users with poor network connections.
    Default: 0
--RemoteMappingKernelManager.cull_interval=<Int>
    The interval (in seconds) on which to check for idle kernels exceeding the
    cull timeout value.
    Default: 300
--RemoteMappingKernelManager.default_kernel_name=<Unicode>
    The name of the default kernel to start
    Default: 'python3'
--RemoteMappingKernelManager.kernel_info_timeout=<Float>
    Timeout for giving up on a kernel (in seconds). On starting and restarting
    kernels, we check whether the kernel is running and responsive by sending
    kernel_info_requests. This sets the timeout in seconds for how long the
    kernel can take before being presumed dead. This affects the
    MappingKernelManager (which handles kernel restarts) and the
    ZMQChannelsHandler (which handles the startup).
    Default: 60
--RemoteMappingKernelManager.kernel_manager_class=<DottedObjectName>
    The kernel manager class.  This is configurable to allow subclassing of the
    AsyncKernelManager for customized behavior.
    Default: 'jupyter_client.ioloop.AsyncIOLoopKernelManager'
--RemoteMappingKernelManager.root_dir=<Unicode>
    Default: ''
--RemoteMappingKernelManager.shared_context=<Bool>
    Share a single zmq.Context to talk to all my kernels
    Default: True
```
