# Additional environment variables

Besides those environment variables associated with configurable options, the following environment variables can also be used to influence functionality:

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
    The eg-clusterrole.yaml file creates the cluster role 'kernel-controller'
    and conveys that name via EG_KERNEL_CLUSTER_ROLE.  Should the deployment script
    not set this valuem, Enterprise Gateway will then use 'cluster-admin'.  It is
    recommended this value be set to something other than 'cluster-admin'.

  EG_KERNEL_LAUNCH_TIMEOUT=30
    The time (in seconds) Enterprise Gateway will wait for a kernel's startup
    completion status before deeming the startup a failure, at which time a second
    startup attempt will take place.  If a second timeout occurs, Enterprise
    Gateway will report a failure to the client.

  EG_KERNEL_INFO_TIMEOUT=60
    The time (in seconds) Enterprise Gateway will wait for kernel info response
    before deeming the request a failure.

  EG_SENSITIVE_ENV_KEYS=""
    A comma separated list (e.g. "secret,pwd,auth") of sensitive environment
    variables. Any environment variables that contain any of the words from this
    list will have their values as EG_REDACTION_MASK whenever logged.

  EG_REDACTION_MASK=********
    The redaction mask used if EG_SENSITIVE_ENV_KEYS is set. Sensitive environment
    variables will be logged as this redaction mask instead.

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
    namespace is created prior to deployment, and is set into the EG_NAMESPACE env via
    deployment.yaml script. This value is then used within Enterprise Gateway to coordinate
    kernel configurations. Should this value not be set during deployment, Enterprise
    Gateway will default its value to namespace 'default'.

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
    The path to a .pem or any other custom truststore used as a CA bundle in
    yarn-api-client.

  EG_ZMQ_IO_THREADS=1
    The size of the ZMQ thread pool used to handle I/O operations.  Applies only to shared
    contexts which are enabled by default but can be specified via
    `RemoteMappingKernelManager.shared_context = True`.

  EG_ZMQ_MAX_SOCKETS=1023
    Specifies the maximum number of sockets to allow on the ZMQ context.  Applies only to
    shared contexts which are enabled by default but can be specified via
    `RemoteMappingKernelManager.shared_context = True`.
```
