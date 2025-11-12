# Using Jupyter Server's `GatewayKernelManager`

Another way to expose other Jupyter applications like `nbclient` or `papermill` to remote kernels is to use the [`GatewayKernelManager`](https://github.com/jupyter-server/jupyter_server/blob/745f5ba3f00280c1e1900326a7e08463d48a3912/jupyter_server/gateway/managers.py#L317) (and, implicitly, [`GatewayKernelClient`](https://github.com/jupyter-server/jupyter_server/blob/745f5ba3f00280c1e1900326a7e08463d48a3912/jupyter_server/gateway/managers.py#L562)) classes that are embedded in Jupyter Server.

These classes essentially emulate the lower level [`KernelManager`](https://github.com/jupyter/jupyter_client/blob/10decd25308c306b6005cbf271b96493824a83e8/jupyter_client/manager.py#L84) and [`KernelClient`](https://github.com/jupyter/jupyter_client/blob/10decd25308c306b6005cbf271b96493824a83e8/jupyter_client/client.py#L75) classes but _forward_ their requests to/from a configured gateway server. Their necessary configuration for interacting with the gateway server is set on the [`GatewayClient` configurable](../users/client-config.md#gateway-client-configuration).

This allows for the _hosting application_ to remain **outside** the resource-managed cluster since the kernel is actually being managed by the target gateway server.

So, using the previous example, one my have...

```python
import nbformat
from nbclient import NotebookClient
from jupyter_server.gateway.gateway_client import GatewayClient
from jupyter_server.gateway.managers import GatewayKernelManager

with open("my_notebook.ipynb") as fp:
    test_notebook = nbformat.read(fp, as_version=4)

# Set any other gateway-specific parameters on the GatewayClient (singleton) instance
gw_client = GatewayClient.instance()
gw_client.url = "http://my-gateway-server.com:8888"

client = NotebookClient(nb=test_notebook, kernel_manager_class=GatewayKernelManager)
client.execute(kernel_name='my_remote_kernel')
```

In this case, `my_remote_kernel`'s kernel specification file actually resides on the Gateway server. `NotebookClient` will _think_ its talking to local `KernelManager` and `KernelClient` instances, when, in actuality, they are forwarding requests to (and getting response from) the Gateway server at 'http://my-gateway-server.com:8888'.
