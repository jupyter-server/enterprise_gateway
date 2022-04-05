# Gateway Client Configuration

The set of Gateway Client configuration options include the following. To get the current set of supported options, run the following:

```bash
jupyter server --help-all
```

or

```bash
jupyter server --generate-config
```

The following is produced from the `--help-all` option. To determine the corresponding configuration file option, replace `--` with `c.`.

```
--GatewayClient.auth_scheme=<Unicode>
    The auth scheme, added as a prefix to the authorization token used in the HTTP headers.
            (JUPYTER_GATEWAY_AUTH_SCHEME env var)
    Default: None
--GatewayClient.auth_token=<Unicode>
    The authorization token used in the HTTP headers. The header will be
    formatted as::
                {
                    'Authorization': '{auth_scheme} {auth_token}'
                }
            (JUPYTER_GATEWAY_AUTH_TOKEN env var)
    Default: None
--GatewayClient.ca_certs=<Unicode>
    The filename of CA certificates or None to use defaults.
    (JUPYTER_GATEWAY_CA_CERTS env var)
    Default: None
--GatewayClient.client_cert=<Unicode>
    The filename for client SSL certificate, if any.
    (JUPYTER_GATEWAY_CLIENT_CERT env var)
    Default: None
--GatewayClient.client_key=<Unicode>
    The filename for client SSL key, if any.  (JUPYTER_GATEWAY_CLIENT_KEY env
    var)
    Default: None
--GatewayClient.connect_timeout=<Float>
    The time allowed for HTTP connection establishment with the Gateway server.
            (JUPYTER_GATEWAY_CONNECT_TIMEOUT env var)
    Default: 40.0
--GatewayClient.env_whitelist=<Unicode>
    A comma-separated list of environment variable names that will be included, along with
             their values, in the kernel startup request.  The corresponding `env_whitelist` configuration
             value must also be set on the Gateway server - since that configuration value indicates which
             environmental values to make available to the kernel. (JUPYTER_GATEWAY_ENV_WHITELIST env var)
    Default: ''
--GatewayClient.gateway_retry_interval=<Float>
    The time allowed for HTTP reconnection with the Gateway server for the first time.
                Next will be JUPYTER_GATEWAY_RETRY_INTERVAL multiplied by two in factor of numbers of retries
                but less than JUPYTER_GATEWAY_RETRY_INTERVAL_MAX.
                (JUPYTER_GATEWAY_RETRY_INTERVAL env var)
    Default: 1.0
--GatewayClient.gateway_retry_interval_max=<Float>
    The maximum time allowed for HTTP reconnection retry with the Gateway server.
                (JUPYTER_GATEWAY_RETRY_INTERVAL_MAX env var)
    Default: 30.0
--GatewayClient.gateway_retry_max=<Int>
    The maximum retries allowed for HTTP reconnection with the Gateway server.
                (JUPYTER_GATEWAY_RETRY_MAX env var)
    Default: 5
--GatewayClient.headers=<Unicode>
    Additional HTTP headers to pass on the request.  This value will be converted to a dict.
              (JUPYTER_GATEWAY_HEADERS env var)
    Default: '{}'
--GatewayClient.http_pwd=<Unicode>
    The password for HTTP authentication.  (JUPYTER_GATEWAY_HTTP_PWD env var)
    Default: None
--GatewayClient.http_user=<Unicode>
    The username for HTTP authentication. (JUPYTER_GATEWAY_HTTP_USER env var)
    Default: None
--GatewayClient.kernels_endpoint=<Unicode>
    The gateway API endpoint for accessing kernel resources
    (JUPYTER_GATEWAY_KERNELS_ENDPOINT env var)
    Default: '/api/kernels'
--GatewayClient.kernelspecs_endpoint=<Unicode>
    The gateway API endpoint for accessing kernelspecs
    (JUPYTER_GATEWAY_KERNELSPECS_ENDPOINT env var)
    Default: '/api/kernelspecs'
--GatewayClient.kernelspecs_resource_endpoint=<Unicode>
    The gateway endpoint for accessing kernelspecs resources
                (JUPYTER_GATEWAY_KERNELSPECS_RESOURCE_ENDPOINT env var)
    Default: '/kernelspecs'
--GatewayClient.request_timeout=<Float>
    The time allowed for HTTP request completion.
    (JUPYTER_GATEWAY_REQUEST_TIMEOUT env var)
    Default: 40.0
--GatewayClient.url=<Unicode>
    The url of the Kernel or Enterprise Gateway server where
            kernel specifications are defined and kernel management takes place.
            If defined, this Notebook server acts as a proxy for all kernel
            management and kernel specification retrieval.  (JUPYTER_GATEWAY_URL env var)
    Default: None
--GatewayClient.validate_cert=<Bool>
    For HTTPS requests, determines if server's certificate should be validated or not.
            (JUPYTER_GATEWAY_VALIDATE_CERT env var)
    Default: True
--GatewayClient.ws_url=<Unicode>
    The websocket url of the Kernel or Enterprise Gateway server.  If not provided, this value
            will correspond to the value of the Gateway url with 'ws' in place of 'http'.  (JUPYTER_GATEWAY_WS_URL env var)
    Default: None
```
