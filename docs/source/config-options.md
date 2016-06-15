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
--KernelGatewayApp.allow_notebook_download=<Bool>
    Default: False
    Optional API to download the notebook source code in notebook-http mode,
    defaults to not allow
--KernelGatewayApp.allow_origin=<Unicode>
    Default: ''
    Sets the Access-Control-Allow-Origin header. (KG_ALLOW_ORIGIN env var)
--KernelGatewayApp.answer_yes=<Bool>
    Default: False
    Answer yes to any prompts.
--KernelGatewayApp.api=<Unicode>
    Default: 'jupyter-websocket'
    Controls which API to expose, that of a Jupyter kernel or the seed
    notebook's, using values "jupyter-websocket" or "notebook-http" (KG_API env
    var)
--KernelGatewayApp.auth_token=<Unicode>
    Default: ''
    Authorization token required for all requests (KG_AUTH_TOKEN env var)
--KernelGatewayApp.base_url=<Unicode>
    Default: ''
    The base path for mounting all API resources (KG_BASE_URL env var)
--KernelGatewayApp.config_file=<Unicode>
    Default: ''
    Full path of a config file.
--KernelGatewayApp.config_file_name=<Unicode>
    Default: ''
    Specify a config file to load.
--KernelGatewayApp.default_kernel_name=<Unicode>
    Default: ''
    The default kernel name when spawning a kernel (KG_DEFAULT_KERNEL_NAME env
    var)
--KernelGatewayApp.expose_headers=<Unicode>
    Default: ''
    Sets the Access-Control-Expose-Headers header. (KG_EXPOSE_HEADERS env var)
--KernelGatewayApp.generate_config=<Bool>
    Default: False
    Generate default config file.
--KernelGatewayApp.ip=<Unicode>
    Default: ''
    IP address on which to listen (KG_IP env var)
--KernelGatewayApp.list_kernels=<Bool>
    Default: False
    Permits listing of the running kernels using API endpoints /api/kernels and
    /api/sessions (KG_LIST_KERNELS env var). Note: Jupyter Notebook allows this
    by default but kernel gateway does not.
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
    Default: 0
    Limits the number of kernel instances allowed to run by this gateway.
    (KG_MAX_KERNELS env var)
--KernelGatewayApp.port=<Int>
    Default: 0
    Port on which to listen (KG_PORT env var)
--KernelGatewayApp.port_retries=<Int>
    Default: 0
    Number of ports to try if the specified port is not available
    (KG_PORT_RETRIES env var)
--KernelGatewayApp.prespawn_count=<Int>
    Default: None
    Number of kernels to prespawn using the default language. (KG_PRESPAWN_COUNT
    env var)
--KernelGatewayApp.seed_uri=<Unicode>
    Default: ''
    Runs the notebook (.ipynb) at the given URI on every kernel launched.
    (KG_SEED_URI env var)
```