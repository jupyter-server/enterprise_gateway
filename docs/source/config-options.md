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

Provisions Jupyter kernels and proxies HTTP/Websocket traffic to them.

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
----------------
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
--EnterpriseGatewayApp.config_file=<Unicode>
    Default: u''
    Full path of a config file.
--EnterpriseGatewayApp.config_file_name=<Unicode>
    Default: u''
    Specify a config file to load.
--EnterpriseGatewayApp.default_kernel_name=<Unicode>
    Default: u''
    Default kernel name when spawning a kernel (KG_DEFAULT_KERNEL_NAME env var)
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
--EnterpriseGatewayApp.ip=<Unicode>
    Default: '127.0.0.1'
    IP address on which to listen (KG_IP env var)
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
--EnterpriseGatewayApp.port=<Integer>
    Default: 8888
    Port on which to listen (KG_PORT env var)
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
--EnterpriseGatewayApp.yarn_endpoint=<Unicode>
    Default: 'http://localhost:8088/ws/v1/cluster'
    The http url for accessing the YARN Resource Manager. (EG_YARN_ENDPOINT env
    var)

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
    Default: {'scala': '//', None: '#'}
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

### Supported environment variables
```
  EG_YARN_ENDPOINT=http://localhost:8088/ws/v1/cluster 
      YARN resource manager endpoint.  This value can also be specified on the 
      command line via option '--EnterpriseGatewayApp.yarn_endpoint'.  

  EG_REMOTE_HOSTS=localhost 
      A comma-separated list of hosts on which DistributedProcessProxy kernels will
      be launched e.g., host1,host2.  Not bracketing or quoting of hostnames is 
      required when setting the env variable.  This value can also be specified on 
      the command line via option '--EnterpriseGatewayApp.remote_hosts', although 
      bracketing and quoting is required in that case.  
 
  EG_ENABLE_TUNNELING=False 
      Indicates whether tunneling (via ssh) of the kernel and communication ports
      is enabled (True) or not (False).  This feature is currently in experimental 
      stages but we intend to flip the default value to True at some point.  
        
  EG_PROXY_LAUNCH_LOG=/tmp/jeg_proxy_launch.log 
      The log file used during remote kernel launches of `DistributedProcessProxy`
      based kernels.  This file should be consulted when kernel operations are not 
      working as expected.  Note that it will contain output from multiple kernels.  
              
  EG_KERNEL_LAUNCH_TIMEOUT=30 
      The time (in seconds) Enterprise Gateway will wait for a kernel's startup 
      completion status before deeming the startup a failure, at which time a second 
      startup attempt will take place.  If a second timeout occurs, Enterprise 
      Gateway will report a failure to the client.  
```
The following environment variables may be useful for troubleshooting:
```
  EG_SSH_LOG_LEVEL=WARNING 
      By default, the `paramiko` ssh library is too verbose for its logging.  This
      value can be adjusted in situations where ssh troubleshooting may be warranted.  

  EG_YARN_LOG_LEVEL=WARNING 
      By default, the `yarn-api-client` library is too verbose for its logging.  This
      value can be adjusted in situations where YARN troubleshooting may be warranted.  

  EG_MAX_POLL_ATTEMPTS=10 
      Polling is used in various places during life-cycle management operations - like 
      determining if a kernel process is still alive, stopping the process, waiting 
      for the process to terminate, etc.  As a result, it may be useful to adjust 
      this value during those kinds of troubleshooting scenarios, although that 
      should rarely be necessary.  

  EG_POLL_INTERVAL=0.5
    The interval (in seconds) to wait before checking poll results again.  

  EG_SOCKET_TIMEOUT=5.0 
    The time (in seconds) the enterprise gateway will wait on its connection
    file socket waiting on return from a remote kernel launcher.  Upon timeout, the 
    operation will be retried immediately, until the overall time limit has been exceeded.   

```

