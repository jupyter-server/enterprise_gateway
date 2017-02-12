## Configuration options

The kernel gateway adheres to the [Jupyter common configuration approach](https://jupyter.readthedocs.io/en/latest/projects/config.html). You can configure an instance of the kernel gateway using:

1. A configuration file
2. Command line parameters
3. Environment variables

To generate a template configuration file, run the following:

```
jupyter kernelgateway --generate-config
```

To see the same configuration options at the command line, run the following:

```
jupyter kernelgateway --help-all
```

A snapshot of this help appears below for ease of reference on the web.

```
Jupyter Kernel Gateway

Provisions Jupyter kernels and proxies HTTP/Websocket traffic to them.

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
--certfile=<Unicode> (KernelGatewayApp.certfile)
    Default: None
    The full path to an SSL/TLS certificate file. (KG_CERTFILE env var)
--config=<Unicode> (JupyterApp.config_file)
    Default: ''
    Full path of a config file.
--port_retries=<Int> (KernelGatewayApp.port_retries)
    Default: 50
    Number of ports to try if the specified port is not available
    (KG_PORT_RETRIES env var)
--ip=<Unicode> (KernelGatewayApp.ip)
    Default: '127.0.0.1'
    IP address on which to listen (KG_IP env var)
--keyfile=<Unicode> (KernelGatewayApp.keyfile)
    Default: None
    The full path to a private key file for usage with SSL/TLS. (KG_KEYFILE env
    var)
--seed_uri=<Unicode> (KernelGatewayApp.seed_uri)
    Default: None
    Runs the notebook (.ipynb) at the given URI on every kernel launched. No
    seed by default. (KG_SEED_URI env var)
--client-ca=<Unicode> (KernelGatewayApp.client_ca)
    Default: None
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (KG_CLIENT_CA env var)
--port=<Int> (KernelGatewayApp.port)
    Default: 8888
    Port on which to listen (KG_PORT env var)
--api=<Unicode> (KernelGatewayApp.api)
    Default: 'kernel_gateway.jupyter_websocket'
    Controls which API to expose, that of a Jupyter notebook server, the seed
    notebook's, or one provided by another module, respectively using values
    'kernel_gateway.jupyter_websocket', 'kernel_gateway.notebook_http', or
    another fully qualified module name (KG_API env var)
--log-level=<Enum> (Application.log_level)
    Default: 30
    Choices: (0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    Set the log level by value or name.

Class parameters
----------------

Parameters are set from command-line arguments of the form:
`--Class.trait=value`. This line is evaluated in Python, so simple expressions
are allowed, e.g.:: `--C.a='range(3)'` For setting C.a=[0,1,2].

KernelGatewayApp options
------------------------
--KernelGatewayApp.allow_credentials=<Unicode>
    Default: ''
    Sets the Access-Control-Allow-Credentials header. (KG_ALLOW_CREDENTIALS env
    var)
--KernelGatewayApp.allow_headers=<Unicode>
    Default: ''
    Sets the Access-Control-Allow-Headers header. (KG_ALLOW_HEADERS env var)
--KernelGatewayApp.allow_methods=<Unicode>
    Default: ''
    Sets the Access-Control-Allow-Methods header. (KG_ALLOW_METHODS env var)
--KernelGatewayApp.allow_origin=<Unicode>
    Default: ''
    Sets the Access-Control-Allow-Origin header. (KG_ALLOW_ORIGIN env var)
--KernelGatewayApp.answer_yes=<Bool>
    Default: False
    Answer yes to any prompts.
--KernelGatewayApp.api=<Unicode>
    Default: 'kernel_gateway.jupyter_websocket'
    Controls which API to expose, that of a Jupyter notebook server, the seed
    notebook's, or one provided by another module, respectively using values
    'kernel_gateway.jupyter_websocket', 'kernel_gateway.notebook_http', or
    another fully qualified module name (KG_API env var)
--KernelGatewayApp.auth_token=<Unicode>
    Default: ''
    Authorization token required for all requests (KG_AUTH_TOKEN env var)
--KernelGatewayApp.base_url=<Unicode>
    Default: '/'
    The base path for mounting all API resources (KG_BASE_URL env var)
--KernelGatewayApp.certfile=<Unicode>
    Default: None
    The full path to an SSL/TLS certificate file. (KG_CERTFILE env var)
--KernelGatewayApp.client_ca=<Unicode>
    Default: None
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (KG_CLIENT_CA env var)
--KernelGatewayApp.config_file=<Unicode>
    Default: ''
    Full path of a config file.
--KernelGatewayApp.config_file_name=<Unicode>
    Default: ''
    Specify a config file to load.
--KernelGatewayApp.default_kernel_name=<Unicode>
    Default: ''
    Default kernel name when spawning a kernel (KG_DEFAULT_KERNEL_NAME env var)
--KernelGatewayApp.expose_headers=<Unicode>
    Default: ''
    Sets the Access-Control-Expose-Headers header. (KG_EXPOSE_HEADERS env var)
--KernelGatewayApp.force_kernel_name=<Unicode>
    Default: ''
    Override any kernel name specified in a notebook or request
    (KG_FORCE_KERNEL_NAME env var)
--KernelGatewayApp.generate_config=<Bool>
    Default: False
    Generate default config file.
--KernelGatewayApp.ip=<Unicode>
    Default: '127.0.0.1'
    IP address on which to listen (KG_IP env var)
--KernelGatewayApp.keyfile=<Unicode>
    Default: None
    The full path to a private key file for usage with SSL/TLS. (KG_KEYFILE env
    var)
--KernelGatewayApp.log_datefmt=<Unicode>
    Default: '%Y-%m-%d %H:%M:%S'
    The date format used by logging formatters for %(asctime)s
--KernelGatewayApp.log_format=<Unicode>
    Default: '[%(name)s]%(highlevel)s %(message)s'
    The Logging format template
--KernelGatewayApp.log_level=<Enum>
    Default: 30
    Choices: (0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    Set the log level by value or name.
--KernelGatewayApp.max_age=<Unicode>
    Default: ''
    Sets the Access-Control-Max-Age header. (KG_MAX_AGE env var)
--KernelGatewayApp.max_kernels=<Int>
    Default: None
    Limits the number of kernel instances allowed to run by this gateway.
    Unbounded by default. (KG_MAX_KERNELS env var)
--KernelGatewayApp.port=<Int>
    Default: 8888
    Port on which to listen (KG_PORT env var)
--KernelGatewayApp.port_retries=<Int>
    Default: 50
    Number of ports to try if the specified port is not available
    (KG_PORT_RETRIES env var)
--KernelGatewayApp.prespawn_count=<Int>
    Default: None
    Number of kernels to prespawn using the default language. No prespawn by
    default. (KG_PRESPAWN_COUNT env var)
--KernelGatewayApp.seed_uri=<Unicode>
    Default: None
    Runs the notebook (.ipynb) at the given URI on every kernel launched. No
    seed by default. (KG_SEED_URI env var)

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
