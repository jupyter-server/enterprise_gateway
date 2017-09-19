## Configuration options

Jupyter Elyra adheres to the 
[Jupyter common configuration approach](https://jupyter.readthedocs.io/en/latest/projects/config.html)
. You can configure an instance of elyra using:

1. A configuration file
2. Command line parameters
3. Environment variables

Note that because Elyra is built on Kernel Gateway, all of the `KernelGatewayApp` options 
can be specified as `ElyraApp` options.  In addition, the `KG_` prefix of environment 
variables has also been perserved.

To generate a template configuration file, run the following:

```
jupyter elyra --generate-config
```

To see the same configuration options at the command line, run the following:

```
jupyter elyra --help-all
```

A snapshot of this help appears below for ease of reference on the web.

```
Jupyter Elyra

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

ElyraApp options
----------------
--ElyraApp.allow_credentials=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Credentials header. (KG_ALLOW_CREDENTIALS env
    var)
--ElyraApp.allow_headers=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Headers header. (KG_ALLOW_HEADERS env var)
--ElyraApp.allow_methods=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Methods header. (KG_ALLOW_METHODS env var)
--ElyraApp.allow_origin=<Unicode>
    Default: u''
    Sets the Access-Control-Allow-Origin header. (KG_ALLOW_ORIGIN env var)
--ElyraApp.answer_yes=<Bool>
    Default: False
    Answer yes to any prompts.
--ElyraApp.api=<Unicode>
    Default: 'kernel_gateway.jupyter_websocket'
    Controls which API to expose, that of a Jupyter notebook server, the seed
    notebook's, or one provided by another module, respectively using values
    'kernel_gateway.jupyter_websocket', 'kernel_gateway.notebook_http', or
    another fully qualified module name (KG_API env var)
--ElyraApp.auth_token=<Unicode>
    Default: u''
    Authorization token required for all requests (KG_AUTH_TOKEN env var)
--ElyraApp.base_url=<Unicode>
    Default: '/'
    The base path for mounting all API resources (KG_BASE_URL env var)
--ElyraApp.certfile=<Unicode>
    Default: None
    The full path to an SSL/TLS certificate file. (KG_CERTFILE env var)
--ElyraApp.client_ca=<Unicode>
    Default: None
    The full path to a certificate authority certificate for SSL/TLS client
    authentication. (KG_CLIENT_CA env var)
--ElyraApp.config_file=<Unicode>
    Default: u''
    Full path of a config file.
--ElyraApp.config_file_name=<Unicode>
    Default: u''
    Specify a config file to load.
--ElyraApp.default_kernel_name=<Unicode>
    Default: u''
    Default kernel name when spawning a kernel (KG_DEFAULT_KERNEL_NAME env var)
--ElyraApp.expose_headers=<Unicode>
    Default: u''
    Sets the Access-Control-Expose-Headers header. (KG_EXPOSE_HEADERS env var)
--ElyraApp.force_kernel_name=<Unicode>
    Default: u''
    Override any kernel name specified in a notebook or request
    (KG_FORCE_KERNEL_NAME env var)
--ElyraApp.generate_config=<Bool>
    Default: False
    Generate default config file.
--ElyraApp.ip=<Unicode>
    Default: '127.0.0.1'
    IP address on which to listen (KG_IP env var)
--ElyraApp.keyfile=<Unicode>
    Default: None
    The full path to a private key file for usage with SSL/TLS. (KG_KEYFILE env
    var)
--ElyraApp.log_datefmt=<Unicode>
    Default: '%Y-%m-%d %H:%M:%S'
    The date format used by logging formatters for %(asctime)s
--ElyraApp.log_format=<Unicode>
    Default: '[%(name)s]%(highlevel)s %(message)s'
    The Logging format template
--ElyraApp.log_level=<Enum>
    Default: 30
    Choices: (0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
    Set the log level by value or name.
--ElyraApp.max_age=<Unicode>
    Default: u''
    Sets the Access-Control-Max-Age header. (KG_MAX_AGE env var)
--ElyraApp.max_kernels=<Integer>
    Default: None
    Limits the number of kernel instances allowed to run by this gateway.
    Unbounded by default. (KG_MAX_KERNELS env var)
--ElyraApp.port=<Integer>
    Default: 8888
    Port on which to listen (KG_PORT env var)
--ElyraApp.port_retries=<Integer>
    Default: 50
    Number of ports to try if the specified port is not available
    (KG_PORT_RETRIES env var)
--ElyraApp.prespawn_count=<Integer>
    Default: None
    Number of kernels to prespawn using the default language. No prespawn by
    default. (KG_PRESPAWN_COUNT env var)
--ElyraApp.seed_uri=<Unicode>
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
