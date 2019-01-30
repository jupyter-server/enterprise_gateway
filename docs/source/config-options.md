## Configuration options

Jupyter Enterprise Gateway adheres to the 
[Jupyter common configuration approach](https://jupyter.readthedocs.io/en/latest/projects/config.html)
. You can configure an instance of Enterprise Gateway using:

1. A configuration file
2. Command line parameters
3. Environment variables

Note that because Enterprise Gateway is built on Kernel Gateway, all of the `KernelGatewayApp` options 
can be specified as `EnterpriseGatewayApp` options.  In addition, the `KG_` prefix of inherited environment 
variables has also been preserved, while those variables introduced by Enterprise Gateway will be
prefixed with `EG_`.

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
-y
    Answer yes to any questions instead of prompting.
--generate-config
    generate default config file
--certfile=<Unicode> (KernelGatewayApp.certfile)
    Default: None
    The full path to an SSL/TLS certificate file. (KG_CERTFILE env var)
--seed_uri=<Unicode> (KernelGatewayApp.seed_uri)
    Default: None
    Runs the notebook (.ipynb) at the given URI on every kernel launched. No
    seed by default. (KG_SEED_URI env var)
--ip=<Unicode> (KernelGatewayApp.ip)
    Default: '127.0.0.1'
    IP address on which to listen (KG_IP env var)
--log-level=<Enum> (Application.log_level)
    Default: 30
    Choices: (0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    Set the log level by value or name.
--port=<Integer> (KernelGatewayApp.port)
    Default: 8888
    Port on which to listen (KG_PORT env var)
--api=<Unicode> (KernelGatewayApp.api)
    Default: 'kernel_gateway.jupyter_websocket'
    Controls which API to expose, that of a Jupyter notebook server, the seed
    notebook's, or one provided by another module, respectively using values
    'kernel_gateway.jupyter_websocket', 'kernel_gateway.notebook_http', or
    another fully qualified module name (KG_API env var)
--port_retries=<Integer> (KernelGatewayApp.port_retries)
    Default: 50
    Number of ports to try if the specified port is not available
    (KG_PORT_RETRIES env var)
--client-ca=<Unicode> (KernelGatewayApp.client_ca)
    Default: None
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (KG_CLIENT_CA env var)
--config=<Unicode> (JupyterApp.config_file)
    Default: u''
    Full path of a config file.
--keyfile=<Unicode> (KernelGatewayApp.keyfile)
    Default: None
    The full path to a private key file for usage with SSL/TLS. (KG_KEYFILE env
    var)

Class parameters
----------------

Parameters are set from command-line arguments of the form:
`--Class.trait=value`. This line is evaluated in Python, so simple expressions
are allowed, e.g.:: `--C.a='range(3)'` For setting C.a=[0,1,2].

EnterpriseGatewayApp options
----------------------------
--EnterpriseGatewayApp.allow_credentials=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Credentials header. (KG_ALLOW_CREDENTIALS env
    var)
--EnterpriseGatewayApp.allow_headers=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Headers header. (KG_ALLOW_HEADERS env var)
--EnterpriseGatewayApp.allow_methods=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Methods header. (KG_ALLOW_METHODS env var)
--EnterpriseGatewayApp.allow_origin=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Origin header. (KG_ALLOW_ORIGIN env var)
--EnterpriseGatewayApp.answer_yes=<Bool>
    Default: False
    Answer yes to any prompts.
--EnterpriseGatewayApp.api=<Unicode>
    Default: 'kernel_gateway.jupyter_websocket'
    Controls which API to expose, that of a Jupyter notebook server, the seed
    notebook's, or one provided by another module, respectively using values
    'kernel_gateway.jupyter_websocket', 'kernel_gateway.notebook_http', or
    another fully qualified module name (KG_API env var)
--EnterpriseGatewayApp.auth_token=<Unicode>
    Default: u''
    Authorization token required for all requests (KG_AUTH_TOKEN env var)
--EnterpriseGatewayApp.authorized_users=<Set>
    Default: set([])
    Comma-separated list of user names (e.g., ['bob','alice']) against which
    KERNEL_USERNAME will be compared.  Any match (case-sensitive) will allow the
    kernel's launch, otherwise an HTTP 403 (Forbidden) error will be raised.
    The set of unauthorized users takes precedence. This option should be used
    carefully as it can dramatically limit who can launch kernels.
    (EG_AUTHORIZED_USERS env var - non-bracketed, just comma-separated)
--EnterpriseGatewayApp.base_url=<Unicode>
    Default: '/'
    The base path for mounting all API resources (KG_BASE_URL env var)
--EnterpriseGatewayApp.certfile=<Unicode>
    Default: None
    The full path to an SSL/TLS certificate file. (KG_CERTFILE env var)
--EnterpriseGatewayApp.client_ca=<Unicode>
    Default: None
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (KG_CLIENT_CA env var)
--EnterpriseGatewayApp.conductor_endpoint=<Unicode>
    Default: None
    The http url for accessing the Conductor REST API. (EG_CONDUCTOR_ENDPOINT
    env var)
--EnterpriseGatewayApp.config_file=<Unicode>
    Default: u''
    Full path of a config file.
--EnterpriseGatewayApp.config_file_name=<Unicode>
    Default: u''
    Specify a config file to load.
--EnterpriseGatewayApp.default_kernel_name=<Unicode>
    Default: u''
    Default kernel name when spawning a kernel (KG_DEFAULT_KERNEL_NAME env var)
--EnterpriseGatewayApp.env_process_whitelist=<List>
    Default: []
    Environment variables allowed to be inherited from the spawning process by
    the kernel
--EnterpriseGatewayApp.expose_headers=<Unicode>
    Default: u''
    Sets the Access-Control-Expose-Headers header. (KG_EXPOSE_HEADERS env var)
--EnterpriseGatewayApp.force_kernel_name=<Unicode>
    Default: u''
    Override any kernel name specified in a notebook or request
    (KG_FORCE_KERNEL_NAME env var)
--EnterpriseGatewayApp.generate_config=<Bool>
    Default: False
    Generate default config file.
--EnterpriseGatewayApp.impersonation_enabled=<Bool>
    Default: False
    Indicates whether impersonation will be performed during kernel launch.
    (EG_IMPERSONATION_ENABLED env var)
--EnterpriseGatewayApp.ip=<Unicode>
    Default: '127.0.0.1'
    IP address on which to listen (KG_IP env var)
--EnterpriseGatewayApp.kernel_manager_class=<Type>
    Default: 'enterprise_gateway.services.kernels.remotemanager.RemoteMapp...
    The kernel manager class to use. Should be a subclass of
    `notebook.services.kernels.MappingKernelManager`.
--EnterpriseGatewayApp.kernel_spec_manager_class=<Type>
    Default: 'enterprise_gateway.services.kernelspecs.remotekernelspec.Rem...
    The kernel spec manager class to use. Should be a subclass of
    `jupyter_client.kernelspec.KernelSpecManager`.
--EnterpriseGatewayApp.keyfile=<Unicode>
    Default: None
    The full path to a private key file for usage with SSL/TLS. (KG_KEYFILE env
    var)
--EnterpriseGatewayApp.log_datefmt=<Unicode>
    Default: '%Y-%m-%d %H:%M:%S'
    The date format used by logging formatters for %(asctime)s
--EnterpriseGatewayApp.log_format=<Unicode>
    Default: '[%(name)s]%(highlevel)s %(message)s'
    The Logging format template
--EnterpriseGatewayApp.log_level=<Enum>
    Default: 30
    Choices: (0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    Set the log level by value or name.
--EnterpriseGatewayApp.max_age=<Unicode>
    Default: u''
    Sets the Access-Control-Max-Age header. (KG_MAX_AGE env var)
--EnterpriseGatewayApp.max_kernels=<Integer>
    Default: None
    Limits the number of kernel instances allowed to run by this gateway.
    Unbounded by default. (KG_MAX_KERNELS env var)
--EnterpriseGatewayApp.max_kernels_per_user=<Integer>
    Default: -1
    Specifies the maximum number of kernels a user can have active
    simultaneously.  A value of -1 disables enforcement.
    (EG_MAX_KERNELS_PER_USER env var)
--EnterpriseGatewayApp.port=<Integer>
    Default: 8888
    Port on which to listen (KG_PORT env var)
--EnterpriseGatewayApp.port_range=<Unicode>
    Default: '0..0'
    Specifies the lower and upper port numbers from which ports are created.
    The bounded values are separated by '..' (e.g., 33245..34245 specifies a
    range of 1000 ports to be randomly selected). A range of zero (e.g.,
    33245..33245 or 0..0) disables port-range enforcement.  (EG_PORT_RANGE env
    var)
--EnterpriseGatewayApp.port_retries=<Integer>
    Default: 50
    Number of ports to try if the specified port is not available
    (KG_PORT_RETRIES env var)
--EnterpriseGatewayApp.prespawn_count=<Integer>
    Default: None
    Number of kernels to prespawn using the default language. No prespawn by
    default. (KG_PRESPAWN_COUNT env var)
--EnterpriseGatewayApp.remote_hosts=<List>
    Default: ['localhost']
    Bracketed comma-separated list of hosts on which DistributedProcessProxy
    kernels will be launched e.g., ['host1','host2']. (EG_REMOTE_HOSTS env var -
    non-bracketed, just comma-separated)
--EnterpriseGatewayApp.seed_uri=<Unicode>
    Default: None
    Runs the notebook (.ipynb) at the given URI on every kernel launched. No
    seed by default. (KG_SEED_URI env var)
--EnterpriseGatewayApp.trust_xheaders=<CBool>
    Default: False
    Use x-* header values for overriding the remote-ip, useful when application
    is behing a proxy. (KG_TRUST_XHEADERS env var)
--EnterpriseGatewayApp.unauthorized_users=<Set>
    Default: set(['root'])
    Comma-separated list of user names (e.g., ['root','admin']) against which
    KERNEL_USERNAME will be compared.  Any match (case-sensitive) will prevent
    the kernel's launch and result in an HTTP 403 (Forbidden) error.
    (EG_UNAUTHORIZED_USERS env var - non-bracketed, just comma-separated)
--EnterpriseGatewayApp.yarn_endpoint=<Unicode>
    Default: 'http://localhost:8088/ws/v1/cluster'
    The http url for accessing the YARN Resource Manager. (EG_YARN_ENDPOINT env
    var)
--EnterpriseGatewayApp.yarn_endpoint_security_enabled=<Bool>
    Default: False
    Is YARN Kerberos/SPNEGO Security enabled (True/False).
    (EG_YARN_ENDPOINT_SECURITY_ENABLED env var)

NotebookHTTPPersonality options
-------------------------------
--NotebookHTTPPersonality.allow_notebook_download=<Bool>
    Default: False
    Optional API to download the notebook source code in notebook-http mode,
    defaults to not allow
--NotebookHTTPPersonality.cell_parser=<Unicode>
    Default: 'kernel_gateway.notebook_http.cell.parser'
    Determines which module is used to parse the notebook for endpoints and
    documentation. Valid module names include
    'kernel_gateway.notebook_http.cell.parser' and
    'kernel_gateway.notebook_http.swagger.parser'. (KG_CELL_PARSER env var)
--NotebookHTTPPersonality.comment_prefix=<Dict>
    Default: {None: '#', 'scala': '//'}
    Maps kernel language to code comment syntax
--NotebookHTTPPersonality.static_path=<Unicode>
    Default: None
    Serve static files on disk in the given path as /public, defaults to not
    serve

JupyterWebsocketPersonality options
-----------------------------------
--JupyterWebsocketPersonality.env_whitelist=<List>
    Default: []
    Environment variables allowed to be set when a client requests a new kernel
--JupyterWebsocketPersonality.list_kernels=<Bool>
    Default: False
    Permits listing of the running kernels using API endpoints /api/kernels and
    /api/sessions (KG_LIST_KERNELS env var). Note: Jupyter Notebook allows this
    by default but kernel gateway does not.
```

### Addtional supported environment variables
```
  EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME=default
    Kubernetes only.  This value indicates the default service account name to use for kernel
    namespaces when the Enterprise Gateway needs to create the kernel's namespace and
    KERNEL_SERVICE_ACCOUNT_NAME has not been provided.

  EG_DOCKER_NETWORK=enterprise-gateway or bridge
    Docker only. Used by the docker deployment and launch scripts, this indicates the name of the
    docker network docker network to use.  The start scripts default this value to 'enterprise-gateway'
    because they create the network.  The docker kernel launcher (launch_docker.py) defaults
    this value to 'bridge' only in cases where it wasn't previously set by the deployment script.

  EG_ENABLE_TUNNELING=False
    Indicates whether tunneling (via ssh) of the kernel and communication ports
    is enabled (True) or not (False).

  EG_KERNEL_CLUSTER_ROLE=kernel-controller or cluster-admin
    Kubernetes only.  The role to use when binding with the kernel service account.  The
    enterprise-gateway.yaml script creates the cluster role 'kernel-controller' and conveys that
    name via EG_KERNEL_CLUSTER_ROLE.  Should the deployment script not set this valuem, Enterprise
    Gateway will then use 'cluster-admin'.  It is recommended this value be set to something other
    than 'cluster-admin'.
              
  EG_KERNEL_LAUNCH_TIMEOUT=30 
    The time (in seconds) Enterprise Gateway will wait for a kernel's startup
    completion status before deeming the startup a failure, at which time a second
    startup attempt will take place.  If a second timeout occurs, Enterprise
    Gateway will report a failure to the client.

  EG_KERNEL_LOG_DIR=/tmp
    The directory used during remote kernel launches of DistributedProcessProxy
    kernels.  Files in this directory will be of the form kernel-<kernel_id>.log.

  EG_KERNEL_SESSION_LOCATION=<JupyterDataDir>
    EXPERIMENTAL - The location in which the kernel session information is persisted.
    By default, this is located in the configured JupyterDataDir.

  EG_LOCAL_IP_BLACKLIST=''
    A comma-separated list of local IPv4 addresses (or regular expressions) that
    should not be used when determining the response address used to convey connection
    information back to Enterprise Gateway from a remote kernel.  In some cases, other
    network interfaces (e.g., docker with 172.17.0.*) can interfere - leading to
    connection failures during kernel startup.
    Example: EG_LOCAL_IP_BLACKLIST=172.17.0.*,192.168.0.27 will eliminate the use of
    all addresses in 172.17.0 as well as 192.168.0.27
      
  EG_MAX_PORT_RANGE_RETRIES=5
    The number of attempts made to locate an available port within the specified
    port range.  Only applies when --EnterpriseGatewayApp.port_range
    (or EG_PORT_RANGE) has been specified or is in use for the given kernel.
            
  EG_MIN_PORT_RANGE_SIZE=1000
    The minimum port range size permitted when --EnterpriseGatewayApp.port_range
    (or EG_PORT_RANGE) is specified or is in use for the given kernel.  Port ranges
    reflecting smaller sizes will result in a failure to launch the corresponding
    kernel (since port-range can be specified within individual kernel specifications).
      
  EG_NAMESPACE=enterprise-gateway or default
    Kubernetes only.  Used during Kubernetes deployment, this indicates the name of the
    namespace in which the Enterprise Gateway service is deployed.  The enterprise-gateway.yaml
    file creates this namespace, then sets EG_NAMESPACE dring deployment.
    This value is then used within Enterprise Gateway to coordinate kernel configurations.
    Should this value not be set during deployment, Enterprise Gateway will default its
    value to namespace 'default'.
      
  EG_SHARED_NAMESPACE=False
    Kubernetes only. This value indicates whether (True) or not (False) all kernel pods should
    reside in the same namespace as Enterprise Gateway.  This is not a recommended configuration.

  EG_SSH_PORT=22
    The port number used for ssh operations for installations choosing to
    configure the ssh server on a port other than the default 22.
```
The following environment variables may be useful for troubleshooting:
```
  EG_DOCKER_LOG_LEVEL=WARNING
    By default, the docker client library is too verbose for its logging.  This
    value can be adjusted in situations where docker troubleshooting may be warranted.

  EG_KUBERNETES_LOG_LEVEL=WARNING
    By default, the kubernetes client library is too verbose for its logging.  This
    value can be adjusted in situations where kubernetes troubleshooting may be warranted.

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
    operation will be retried immediately, until the overall time limit has been exceeded.   

  EG_SSH_LOG_LEVEL=WARNING
    By default, the paramiko ssh library is too verbose for its logging.  This
    value can be adjusted in situations where ssh troubleshooting may be warranted.

  EG_YARN_LOG_LEVEL=WARNING
    By default, the yarn-api-client library is too verbose for its logging.  This
    value can be adjusted in situations where YARN troubleshooting may be warranted.
```

The following environment variables are managed by Enterprise Gateway and listed here for completeness.  Warning: Setting these variables manually could adversely affect operations.
```
  EG_DOCKER_MODE
    Docker only.  Used by launch_docker.py to determine if the kernel container should be created
    using the swarm service API or the regular docker container API.  Enterprise Gateway sets this
    value depending on whether the kernel is using the DockerSwarmProcessProxy or DockerProcessProxy.

  EG_RESPONSE_ADDRESS
    This value is set during each kernel launch and resides in the environment of the kernel launch process.
    Its value represents the address to which the remote kernel's connection information should be
    sent.  Enterprise Gateway is listening on that socket and will close the socket once the remote
    kernel launcher has conveyed the appropriate information.
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
```
  KERNEL_EXECUTOR_IMAGE=<from kernel.json process-proxy stanza> or KERNEL_IMAGE
    Kubernetees Spark only. This indicates the image that Spark on Kubernetes will use for the its
    executors.  Although this value could come from the user, its strongly recommended that the
    process-proxy stanza of the corresponding kernel's kernelspec (kernel.json) file be updated
    to include the image name.  If no image name is provided, the value of KERNEL_IMAGE will be used.

  KERNEL_ID=<from user> or <system generated>
    This value represents the identifier used by the Jupyter framework to identify the kernel.  Although
    this value could be provided by the user, it is recommended that it be generated by the system.

  KERNEL_IMAGE=<from user> or <from kernel.json process-proxy stanza>
    Containers only. This indicates the image to use for the kernel in containerized environments -
    Kubernetes or Docker.  Although it can be provided by the user, it is strongly recommended that
    the process-proxy stanza of the corresponding kernel's kernelspec (kernel.json) file be updated
    to include the image name.

  KERNEL_LAUNCH_TIMEOUT=<from user> or EG_KERNEL_LAUNCH_TIMEOUT
    Indicates the time (in seconds) to allow for a kernel's launch.  This value should be submitted
    in the kernel startup if that particular kernel's startup time is expected to exceed that of
    the EG_KERNEL_LAUNCH_TIMEOUT set when Enterprise Gateway starts.

  KERNEL_NAMESPACE=<from user> or KERNEL_USERNAME-KERNEL_ID or EG_NAMESPACE
    Kubernetes only.  This indicates the name of the namespace to use or create on Kubernetes in
    which the kernel pod will be located.  For users wishing to use a pre-created namespace, this
    value should be submitted in the kernel startup request.  In such cases, the user must also
    provide KERNEL_SERVICE_ACCOUNT_NAME.  If not provided, Enterprise Gateway will create a new
    namespace for the kernel whose value is derived from KERNEL_USERNAME and KERNEL_ID separated
    by a hyphen ('-').  In rare cases where EG_SHARED_NAMESPACE is True, this value will be set
    to the value of EG_NAMESPACE.

    Note that if the namespace is created by Enterprise Gateway, it will be removed upon the
    kernel's termination.  Otherwise, the Enterprise Gateway will not remove the namespace.

  KERNEL_SERVICE_ACCOUNT_NAME=<from user> or EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME
    Kubernetes only.  This value represents the name of the service account that Enterprise Gateway
    should equate with the kernel pod.  If Enterprise Gateway creates the kernel's namespace, it
    will be associated with the cluster role identified by EG_KERNEL_CLUSTER_ROLE.  If not provided,
    it will be derived from EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME.

  KERNEL_USERNAME=<from user> or <enterprise-gateway-user>
    This value represents the logical name of the user submitted the request to start the kernel.
    Of all the KERNEL_ variables, KERNEL_USERNAME is the one that should be submitted in the
    request. In environments in which impersonation is used it represents the target of the
    impersonation.
```

The following kernel-specific environment variables are managed within Enterprise Gateway, but there's nothing preventing them from being set by the client.  As a result, caution should be used if setting these variables manually.
```
  KERNEL_LANGUAGE=<from language entry of kernel.json>
    This indicates the language of the kernel.  It comes from the language entry of the corresponding
    kernel.json file.  This value is used within the start script of the kernel containers, in conjunction
    with KERNEL_LAUNCHERS_DIR, in order to determine which launcher and kernel to start when the container
    is started.

  KERNEL_LAUNCHERS_DIR=/usr/local/bin
    Containers only.  This value is used within the start script of the kernel containers, in conjunction
    with KERNEL_LANGUAGE, to determine where the appropriate kernel launcher is located.

  KERNEL_SPARK_CONTEXT_INIT_MODE=<from argv stanza of kernel.json> or none
    Spark containers only.  This variables exists to convey to the kernel container's launch script the
    mode of Spark context intiatilization it should apply when starting the spark-based kernel container.
```
