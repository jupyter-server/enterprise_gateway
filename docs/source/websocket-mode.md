## `jupyter-websocket` Mode

The `KernelGatewayApp.api` command line argument defaults to `kernel_gateway.jupyter_websocket`. This mode, or *personality*, has the kernel gateway expose:

1. a superset of the HTTP API provided by the Jupyter Notebook server, and
2. the equivalent Websocket API implemented by the Jupyter Notebook server.

### HTTP Resources

The HTTP API consists of kernel, session, monitoring, and metadata resources. All of these are documented in a [swagger.yaml](https://github.com/jupyter/kernel_gateway/blob/master/kernel_gateway/jupyter_websocket/swagger.yaml) file. You can use the [Swagger UI](http://petstore.swagger.io) to interact with a running instance of the kernel gateway by pointing the tool to the `/api/swagger.json` resource.

### Websocket Resources

The `/api/kernels/{kernel_id}/channels` resource multiplexes the [Jupyter kernel messaging protocol](https://jupyter-client.readthedocs.io/en/latest/messaging.html) over a single Websocket connection.

See the [NodeJS](https://github.com/jupyter/kernel_gateway_demos/tree/master/node_client_example) and [Python](https://github.com/jupyter/kernel_gateway_demos/tree/master/python_client_example) client demos for two simple examples of using these resources to send code to kernels for interactive evaluation.
