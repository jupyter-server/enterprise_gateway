## Standalone Remote Kernel Execution 
##### a.k.a "Library Mode"

Remote kernels can be executed by using the `RemoteKernelManager` class directly. This enables running kernels using `ProcessProxy`s without the Enterprise Gateway Webapp.

This can be useful in niche situations, for example, using [nbconvert](https://nbconvert.readthedocs.io/) or [nbclient](https://nbclient.readthedocs.io/) to execute a kernel on a remote cluster.

Sample code using nbclient 0.2.0:

```python
import nbformat
from nbclient import NotebookClient
from enterprise_gateway.services.kernels.remotemanager import RemoteKernelManager

with open("my_notebook.ipynb") as fp:
    test_notebook = nbformat.read(fp, as_version=4)

client = NotebookClient(nb=test_notebook, kernel_manager_class=RemoteKernelManager)
client.execute()
```

The above code will execute the notebook on a kernel using the configured `ProcessProxy` (defaults to Kubernetes).
