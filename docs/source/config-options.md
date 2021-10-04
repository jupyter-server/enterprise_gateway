## Configuration options

Jupyter Enterprise Gateway adheres to
[Jupyter's common configuration approach](https://jupyter.readthedocs.io/en/latest/use/config.html)
. You can configure an instance of Enterprise Gateway using:

1. A configuration file (recommended)
2. Command line parameters
3. Environment variables

See [Dynamic Configurables](#dynamic-configurables) for additional information.

To generate a template configuration file, run the following:

```
jupyter enterprisegateway --generate-config
```

To see the same configuration options at the command line, run the following:

```
jupyter enterprisegateway --help-all
```

A snapshot of this help appears below for ease of reference on the web.  

```
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
    Environment variables allowed to be inherited from the spawning process by
    the kernel. (EG_ENV_PROCESS_WHITELIST env var)
    Default: []
--EnterpriseGatewayApp.env_whitelist=<list-item-1>...
    Environment variables allowed to be set when a client requests a new kernel.
    Use '*' to allow all environment variables sent in the request.
    (EG_ENV_WHITELIST env var)
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
    is behing a proxy. (EG_TRUST_XHEADERS env var)
    Default: False
--EnterpriseGatewayApp.unauthorized_users=<set-item-1>...
    Comma-separated list of user names (e.g., ['root','admin']) against which
    KERNEL_USERNAME will be compared.  Any match (case-sensitive) will prevent
    the kernel's launch and result in an HTTP 403 (Forbidden) error.
    (EG_UNAUTHORIZED_USERS env var - non-bracketed, just comma-separated)
    Default: {'root'}
--EnterpriseGatewayApp.ws_ping_interval=<Int>
    Specifies the ping interval(in seconds) that should be used by zmq port
     associated withspawned kernels.Set this variable to 0 to disable ping mechanism.
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

### Additional supported environment variables
The following environment variables can be used to influence functionality and are not tied to command-line options:
```text
  EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME=default
    Kubernetes only.  This value indicates the default service account name to use for
    kernel namespaces when the Enterprise Gateway needs to create the kernel's namespace
    and KERNEL_SERVICE_ACCOUNT_NAME has not been provided.

  EG_DOCKER_NETWORK=enterprise-gateway or bridge
    Docker only. Used by the docker deployment and launch scripts, this indicates the
    name of the docker network docker network to use.  The start scripts default this
    value to 'enterprise-gateway' because they create the network.  The docker kernel
    launcher (launch_docker.py) defaults this value to 'bridge' only in cases where it
    wasn't previously set by the deployment script.

  EG_ENABLE_TUNNELING=False
    Indicates whether tunneling (via ssh) of the kernel and communication ports
    is enabled (True) or not (False).

  EG_KERNEL_CLUSTER_ROLE=kernel-controller or cluster-admin
    Kubernetes only.  The role to use when binding with the kernel service account.
    The enterprise-gateway.yaml script creates the cluster role 'kernel-controller'
    and conveys that name via EG_KERNEL_CLUSTER_ROLE.  Should the deployment script
    not set this valuem, Enterprise Gateway will then use 'cluster-admin'.  It is
    recommended this value be set to something other than 'cluster-admin'.

  EG_KERNEL_LAUNCH_TIMEOUT=30
    The time (in seconds) Enterprise Gateway will wait for a kernel's startup
    completion status before deeming the startup a failure, at which time a second
    startup attempt will take place.  If a second timeout occurs, Enterprise
    Gateway will report a failure to the client.

  EG_KERNEL_LOG_DIR=/tmp
    The directory used during remote kernel launches of DistributedProcessProxy
    kernels.  Files in this directory will be of the form kernel-<kernel_id>.log.

  EG_KERNEL_SESSION_PERSISTENCE=False
    **Experimental** Enables kernel session persistence.  Currently, this is purely
    experiemental and writes kernel session information to a local file.  Should
    Enterprise Gateway terminate with running kernels, a subsequent restart of
    Enterprise Gateway will attempt to reconnect to the persisted kernels.  See
    also EG_KERNEL_SESSION_LOCATION and --KernelSessionManager.enable_persistence.

  EG_KERNEL_SESSION_LOCATION=<JupyterDataDir>
    **Experimental** The location in which the kernel session information is persisted.
    By default, this is located in the configured JupyterDataDir.  See also
    EG_KERNEL_SESSION_PERSISTENCE.

  EG_MAX_PORT_RANGE_RETRIES=5
    The number of attempts made to locate an available port within the specified
    port range.  Only applies when --EnterpriseGatewayApp.port_range
    (or EG_PORT_RANGE) has been specified or is in use for the given kernel.

  EG_MIN_PORT_RANGE_SIZE=1000
    The minimum port range size permitted when --EnterpriseGatewayApp.port_range
    (or EG_PORT_RANGE) is specified or is in use for the given kernel.  Port ranges
    reflecting smaller sizes will result in a failure to launch the corresponding
    kernel (since port-range can be specified within individual kernel specifications).

  EG_MIRROR_WORKING_DIRS=False
    Containers only.  If True, kernel creation requests that specify KERNEL_WORKING_DIR
    will set the kernel container's working directory to that value.  See also
    KERNEL_WORKING_DIR.

  EG_NAMESPACE=enterprise-gateway or default
    Kubernetes only.  Used during Kubernetes deployment, this indicates the name of
    the namespace in which the Enterprise Gateway service is deployed.  The
    enterprise-gateway.yaml file creates this namespace, then sets EG_NAMESPACE dring
    deployment. This value is then used within Enterprise Gateway to coordinate kernel
    configurations. Should this value not be set during deployment, Enterprise Gateway
    will default its value to namespace 'default'.

  EG_PROHIBITED_GIDS=0
    Containers only.  A comma-separated list of group ids (GID) whose values are not
    allowed to be referenced by KERNEL_GID.  This defaults to the root group id (0).
    Attempts to launch a kernel where KERNEL_GID's value is in this list will result
    in an exception indicating error 403 (Forbidden).  See also EG_PROHIBITED_UIDS.

  EG_PROHIBITED_LOCAL_IPS=''
    A comma-separated list of local IPv4 addresses (or regular expressions) that
    should not be used when determining the response address used to convey connection
    information back to Enterprise Gateway from a remote kernel.  In some cases, other
    network interfaces (e.g., docker with 172.17.0.*) can interfere - leading to
    connection failures during kernel startup.
    Example: EG_PROHIBITED_LOCAL_IPS=172.17.0.*,192.168.0.27 will eliminate the use of
    all addresses in 172.17.0 as well as 192.168.0.27

  EG_PROHIBITED_UIDS=0
    Containers only.  A comma-separated list of user ids (UID) whose values are not
    allowed to be referenced by KERNEL_UID.  This defaults to the root user id (0).
    Attempts to launch a kernel where KERNEL_UID's value is in this list will result
    in an exception indicating error 403 (Forbidden).  See also EG_PROHIBITED_GIDS.

  EG_RESPONSE_IP=None
    Experimental.  The IP address to use to formulate the response address (with 
    `EG_RESPONSE_PORT`).  By default, the server's IP is used.  However, we may find 
    it necessary to use a different IP in cases where the target kernels are external
    to the Enterprise Gateway server (for example).  It's value may also need to be 
    set in cases where the computed (default) is not correct for the current topology.

  EG_RESPONSE_PORT=8877
    The single response port used to receive connection information 
    from launched kernels.

  EG_RESPONSE_PORT_RETRIES=10
    The number of retries to attempt when the original response port
    (EG_RESPONSE_PORT) is found to be in-use.  This value should be 
    set to 0 (zero) if no port retries are desired.
    
  EG_SHARED_NAMESPACE=False
    Kubernetes only. This value indicates whether (True) or not (False) all kernel pods
    should reside in the same namespace as Enterprise Gateway.  This is not a recommended
    configuration.

  EG_SSH_PORT=22
    The port number used for ssh operations for installations choosing to
    configure the ssh server on a port other than the default 22.

  EG_REMOTE_PWD=None
    The password to use to ssh to remote hosts

  EG_REMOTE_USER=None
    The username to use when connecting to remote hosts (default to `getpass.getuser()`
    when not set).

  EG_REMOTE_GSS_SSH=False
    Use gss instead of EG_REMOTE_USER and EG_REMOTE_PWD to connect to remote host via SSH.
    Case insensitive. 'True' to enable, 'False', '' or unset to disable.
    Any other value will error.

  EG_YARN_CERT_BUNDLE=<custom_truststore_path>
    The path to a .pem or any other custom truststore used as a CA bundle in yarn-api-client.
```
### Environment variables that assist in troubleshooting
The following environment variables may be useful for troubleshooting:
```text
  EG_DOCKER_LOG_LEVEL=WARNING
    By default, the docker client library is too verbose for its logging.  This
    value can be adjusted in situations where docker troubleshooting may be warranted.

  EG_KUBERNETES_LOG_LEVEL=WARNING
    By default, the kubernetes client library is too verbose for its logging.  This
    value can be adjusted in situations where kubernetes troubleshooting may be
    warranted.

  EG_LOG_LEVEL=10
    Used by remote launchers and gateway listeners (where the kernel runs), this
    indicates the level of logging used by those entities.  Level 10 (DEBUG) is
    recommended since they don't do verbose logging.

  EG_MAX_POLL_ATTEMPTS=10
    Polling is used in various places during life-cycle management operations - like
    determining if a kernel process is still alive, stopping the process, waiting
    for the process to terminate, etc.  As a result, it may be useful to adjust
    this value during those kinds of troubleshooting scenarios, although that
    should rarely be necessary.

  EG_POLL_INTERVAL=0.5
    The interval (in seconds) to wait before checking poll results again.  

  EG_REMOVE_CONTAINER=True
    Used by launch_docker.py, indicates whether the kernel's docker container should be
    removed following its shutdown.  Set this value to 'False' if you want the container
    to be left around in order to troubleshoot issues.  Remember to set back to 'True'
    to restore normal operation.

  EG_SOCKET_TIMEOUT=5.0
    The time (in seconds) the enterprise gateway will wait on its connection
    file socket waiting on return from a remote kernel launcher.  Upon timeout, the
    operation will be retried immediately, until the overall time limit has been
    exceeded.

  EG_SSH_LOG_LEVEL=WARNING
    By default, the paramiko ssh library is too verbose for its logging.  This
    value can be adjusted in situations where ssh troubleshooting may be warranted.

  EG_YARN_LOG_LEVEL=WARNING
    By default, the yarn-api-client library is too verbose for its logging.  This
    value can be adjusted in situations where YARN troubleshooting may be warranted.
```
### System-owned environment variables
The following environment variables are managed by Enterprise Gateway and listed here for completeness.  WARNING: Manually setting these variables could adversely affect operations.
```text
  EG_DOCKER_MODE
    Docker only.  Used by launch_docker.py to determine if the kernel container
    should be created using the swarm service API or the regular docker container
    API.  Enterprise Gateway sets this value depending on whether the kernel is
    using the DockerSwarmProcessProxy or DockerProcessProxy.

  EG_RESPONSE_ADDRESS
    This value is set during each kernel launch and resides in the environment of
    the kernel launch process. Its value represents the address to which the remote
    kernel's connection information should be sent.  Enterprise Gateway is listening
    on that socket and will associate that connnection information with the responding
    kernel.
```

### Per-kernel Configuration Overrides
As mentioned in the overview of [Process Proxy Configuration](system-architecture.html#process-proxy-configuration)
capabilities, it's possible to override or amend specific system-level configuration values on a per-kernel basis.
The following enumerates the set of per-kernel configuration overrides:

* `remote_hosts`: This process proxy configuration entry can be used to override `--EnterpriseGatewayApp.remote_hosts`.
Any values specified in the config dictionary override the globally defined values.  These apply to all
`DistributedProcessProxy` kernels.
* `yarn_endpoint`: This process proxy configuration entry can be used to override `--EnterpriseGatewayApp.yarn_endpoint`.
Any values specified in the config dictionary override the globally defined values.  These apply to all
`YarnClusterProcessProxy` kernels.  Note that you'll likely be required to specify a different `HADOOP_CONF_DIR`
setting in the kernel.json's `env` stanza in order of the `spark-submit` command to target the appropriate YARN cluster.
* `authorized_users`: This process proxy configuration entry can be used to override
`--EnterpriseGatewayApp.authorized_users`.  Any values specified in the config dictionary override the globally
defined values.  These values apply to **all** process-proxy kernels, including the default `LocalProcessProxy`.  Note
that the typical use-case for this value is to not set `--EnterpriseGatewayApp.authorized_users` at the global level,
but then restrict access at the kernel level.
* `unauthorized_users`: This process proxy configuration entry can be used to **_amend_**
`--EnterpriseGatewayApp.unauthorized_users`.  Any values specified in the config dictionary are **added** to the
globally defined values.  As a result, once a user is denied access at the global level, they will _always be denied
access at the kernel level_.  These values apply to **all** process-proxy kernels, including the default
`LocalProcessProxy`.
* `port_range`: This process proxy configuration entry can be used to override `--EnterpriseGatewayApp.port_range`.
Any values specified in the config dictionary override the globally defined values.  These apply to all
`RemoteProcessProxy` kernels.

### Per-kernel Environment Overrides
In some cases, it is useful to allow specific values that exist in a kernel.json `env` stanza to be
overridden on a per-kernel basis.  For example, if the kernelspec supports resource limitations you
may want to allow some requests to have access to more memory or GPUs than another.  Enterprise
Gateway enables this capability by honoring environment variables provided in the json request over
those same-named variables in the kernel.json `env` stanza.

Environment variables for which this can occur are any variables prefixed with `KERNEL_`
(with the exception of the internal `KERNEL_GATEWAY` variable) as well as any variables
listed in the `--JupyterWebsocketPersonality.env_whitelist` command-line option (or via
the `KG_ENV_WHITELIST` variable).  Locally defined variables listed in `KG_PROCESS_ENV_WHITELIST`
are also honored.

The following kernel-specific environment variables are used by Enterprise Gateway.  As mentioned above, all `KERNEL_` variables submitted in the kernel startup request's json body will be available to the kernel for its launch.
```text
  KERNEL_GID=<from user> or 100
    Containers only. This value represents the group id in which the container will run.
    The default value is 100 representing the users group - which is how all kernel images
    produced by Enterprise Gateway are built.  See also KERNEL_UID.
    Kubernetes: Warning - If KERNEL_GID is set it is strongly recommened that feature-gate
    RunAsGroup be enabled, otherwise, this value will be ignored and the pod will run as
    the root group id.  As a result, the setting of this value into the Security Context
    of the kernel pod is commented out in the kernel-pod.yaml file and must be enabled
    by the administrator.
    Docker: Warning - This value is only added to the supplemental group ids.  As a result,
    if used with KERNEL_UID, the resulting container will run as the root group with this
    value listed in its supplemental groups.

  KERNEL_EXECUTOR_IMAGE=<from kernel.json process-proxy stanza> or KERNEL_IMAGE
    Kubernetees Spark only. This indicates the image that Spark on Kubernetes will use
    for the its executors.  Although this value could come from the user, its strongly
    recommended that the process-proxy stanza of the corresponding kernel's kernelspec
    (kernel.json) file be updated to include the image name.  If no image name is
    provided, the value of KERNEL_IMAGE will be used.

  KERNEL_EXTRA_SPARK_OPTS=<from user>
    Spark only. This variable allows users to add additional spark options to the
    current set of options specified in the corresponding kernel.json file.  This
    variable is purely optional with no default value.  In addition, it is the
    responsibility of the user setting this value to ensure the options passed
    are appropriate relative to the target environment.  Because this variable contains
    space-separate values, it requires appropriate quotation.  For example, to use with
    the notebook docker image jupyterhub/k8s-singleuser-sample , the environment variable would look something like
    this:

    docker run ... -e KERNEL_EXTRA_SPARK_OPTS=\"--conf spark.driver.memory=2g
    --conf spark.executor.memory=2g\" ... jupyterhub/k8s-singleuser-sample

  KERNEL_ID=<from user> or <system generated>
    This value represents the identifier used by the Jupyter framework to identify
    the kernel.  Although this value could be provided by the user, it is recommended
    that it be generated by the system.

  KERNEL_IMAGE=<from user> or <from kernel.json process-proxy stanza>
    Containers only. This indicates the image to use for the kernel in containerized
    environments - Kubernetes or Docker.  Although it can be provided by the user, it
    is strongly recommended that the process-proxy stanza of the corresponding kernel's
    kernelspec (kernel.json) file be updated to include the image name.

  KERNEL_LAUNCH_TIMEOUT=<from user> or EG_KERNEL_LAUNCH_TIMEOUT
    Indicates the time (in seconds) to allow for a kernel's launch.  This value should
    be submitted in the kernel startup if that particular kernel's startup time is
    expected to exceed that of the EG_KERNEL_LAUNCH_TIMEOUT set when Enterprise
    Gateway starts.

  KERNEL_NAMESPACE=<from user> or KERNEL_POD_NAME or EG_NAMESPACE
    Kubernetes only.  This indicates the name of the namespace to use or create on
    Kubernetes in which the kernel pod will be located.  For users wishing to use a
    pre-created namespace, this value should be submitted in the kernel startup
    request.  In such cases, the user must also provide KERNEL_SERVICE_ACCOUNT_NAME.
    If not provided, Enterprise Gateway will create a new namespace for the kernel
    whose value is derived from KERNEL_POD_NAME.  In rare cases where
    EG_SHARED_NAMESPACE is True, this value will be set to the value of EG_NAMESPACE.

    Note that if the namespace is created by Enterprise Gateway, it will be removed
    upon the kernel's termination.  Otherwise, the Enterprise Gateway will not
    remove the namespace.

  KERNEL_POD_NAME=<from user> or KERNEL_USERNAME-KERNEL_ID
    Kubernetes only. By default, Enterprise Gateway will use a kernel pod name whose
    value is derived from KERNEL_USERNAME and KERNEL_ID separated by a hyphen
    ('-').  This variable is typically NOT provided by the user, but, in such
    cases, Enterprise Gateway will honor that value.  However, when provided,
    it is the user's responsibility that KERNEL_POD_NAME is unique relative to
    any pods in the target namespace.  In addition, the pod must NOT exist -
    unlike the case if KERNEL_NAMESPACE is provided.

  KERNEL_SERVICE_ACCOUNT_NAME=<from user> or EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME
    Kubernetes only.  This value represents the name of the service account that
    Enterprise Gateway should equate with the kernel pod.  If Enterprise Gateway
    creates the kernel's namespace, it will be associated with the cluster role
    identified by EG_KERNEL_CLUSTER_ROLE.  If not provided, it will be derived
    from EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME.

  KERNEL_UID=<from user> or 1000
    Containers only. This value represents the user id in which the container will run.
    The default value is 1000 representing the jovyan user - which is how all kernel images
    produced by Enterprise Gateway are built.  See also KERNEL_GID.
    Kubernetes: Warning - If KERNEL_UID is set it is strongly recommened that feature-gate
    RunAsGroup be enabled and KERNEL_GID also be set, otherwise, the pod will run as
    the root group id. As a result, the setting of this value into the Security Context
    of the kernel pod is commented out in the kernel-pod.yaml file and must be enabled
    by the administrator.

  KERNEL_USERNAME=<from user> or <enterprise-gateway-user>
    This value represents the logical name of the user submitted the request to
    start the kernel. Of all the KERNEL_ variables, KERNEL_USERNAME is the one that
    should be submitted in the request. In environments in which impersonation is
    used it represents the target of the impersonation.

  KERNEL_WORKING_DIR=<from user> or None
    Containers only.  This value should model the directory in which the active
    notebook file is running.   It is intended to be used in conjunction with appropriate volume
    mounts in the kernel container such that the user's notebook filesystem exists
    in the container and enables the sharing of resources used within the notebook.
    As a result, the primary use case for this is for Jupyter Hub users running in
    Kubernetes.  When a value is provided and EG_MIRROR_WORKING_DIRS=True, Enterprise
    Gateway will set the container's working directory to the value specified in
    KERNEL_WORKING_DIR.  If EG_MIRROR_WORKING_DIRS is False, KERNEL_WORKING_DIR will
    not be available for use during the kernel's launch.  See also EG_MIRROR_WORKING_DIRS.
```

The following kernel-specific environment variables are managed within Enterprise Gateway, but there's nothing preventing them from being set by the client.  As a result, caution should be used if setting these variables manually.
```text
  KERNEL_LANGUAGE=<from language entry of kernel.json>
    This indicates the language of the kernel.  It comes from the language entry
    of the corresponding kernel.json file.  This value is used within the start
    script of the kernel containers, in conjunction with KERNEL_LAUNCHERS_DIR, in
    order to determine which launcher and kernel to start when the container is
    started.

  KERNEL_LAUNCHERS_DIR=/usr/local/bin
    Containers only.  This value is used within the start script of the kernel
    containers, in conjunction with KERNEL_LANGUAGE, to determine where the
    appropriate kernel launcher is located.

  KERNEL_SPARK_CONTEXT_INIT_MODE=<from argv stanza of kernel.json> or none
    Spark containers only.  This variables exists to convey to the kernel container's
    launch script the mode of Spark context intiatilization it should apply when
    starting the spark-based kernel container.
```
### Dynamic Configurables
Enterprise Gateway now supports the ability to update configuration variables without having to
restart Enterprise Gateway.  This enables the ability to do things like enable debug logging or
adjust the maximum number of kernels per user, all without having to restart Enterprise Gateway.

To enable dynamic configurables configure `EnterpriseGatewayApp.dynamic_config_interval` to a
positive value (default is 0 or disabled).  Since this is the number of seconds to poll Enterprise Gateway's configuration files,
a value greater than 60 (1 minute) is recommended.  This functionality works for most configuration
values, but does have the following caveats:
1. Any configuration variables set on the command line (CLI) or via environment variables are
NOT eligible for dynamic updates.  This is because Jupyter gives those values priority over
file-based configuration variables.
2. Any configuration variables tied to background processing may not reflect their update if
the variable is not *observed* for changes.  For example, the code behind
`MappingKernelManager.cull_idle_timeout` may not reflect changes to the timeout period if
that variable is not monitored (i.e., observed) for changes.
3. Only `Configurables` registered by Enterprise Gateway are eligible for dynamic updates.
Currently, that list consists of the following (and their subclasses): EnterpriseGatewayApp,
MappingKernelManager, KernelSpecManager, and KernelSessionManager.

As a result, administrators are encouraged to configure Enterprise Gateway via configuration
files with only static values configured via the command line or environment.

Note that if `EnterpriseGatewayApp.dynamic_config_interval` is configured with a positive value
via the configuration file (i.e., is eligible for updates) and is subsequently set to 0, then
dynamic configuration updates will be disabled until Enterprise Gateway is restarted with a
positive value.  Therefore, we recommend `EnterpriseGatewayApp.dynamic_config_interval` be
configured via the command line or environment.
