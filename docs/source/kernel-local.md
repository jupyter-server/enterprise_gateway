## Local Deployment

The Local deployment is just for local development and is not meant to be run in real life operations.

If you just want to try EG in a local setup, you can use the following kernelspec:

```json
{
  "display_name": "Python 3 Local",
  "language": "python", 
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.processproxy.LocalProcessProxy"
    }
  },
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_local/scripts/launch_ipykernel.py",
  ]
}
```

with the following `launch_ipykernel.py`.

```python
# ???
pass
```

PS: if Enterprise Gateway encounters a kernelspec without the process_proxy stanza, it will treat that kernelspec as if it contained `LocalProcessProxy.`
