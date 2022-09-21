# Standalone Remote Kernel Execution

Remote kernels can be executed by using the `RemoteKernelManager` class directly. This enables running kernels using `ProcessProxy`s without requiring deployment of the Enterprise Gateway web application. This approach is also known as _Library Mode_.

This can be useful in niche situations, for example, using [nbconvert](https://nbconvert.readthedocs.io/) or [nbclient](https://nbclient.readthedocs.io/) to execute a kernel on a remote cluster.

Sample code using nbclient 0.2.0:

```python
import nbformat
from nbclient import NotebookClient
from enterprise_gateway.services.kernels.remotemanager import RemoteKernelManager

with open("my_notebook.ipynb") as fp:
    test_notebook = nbformat.read(fp, as_version=4)

client = NotebookClient(nb=test_notebook, kernel_manager_class=RemoteKernelManager)
client.execute(kernel_name='my_remote_kernel')
```

The above code will execute the notebook on a kernel named `my_remote_kernel` using its configured `ProcessProxy`.

Depending on the process proxy, the _hosting application_ (e.g., `nbclient`) will likely need to be configured to run on the same network as the remote kernel. So, for example, with Kubernetes, `nbclient` would need to be configured as a Kubernetes POD.
