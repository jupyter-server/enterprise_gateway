# Installing the client

In terms of Enterprise Gateway, the client application is typically JupyterLab or Jupyter Notebook which has an embedded Jupyter Server.
These applications are then configured to connect to Enterprise Gateway and delegate the kernel management operations to the Gateway server ([see Connecting to EG for more details](connecting-to-eg.md)).

To install Jupyter Server via `pip`:

```bash
pip install jupyterlab
```

or via `conda`:

```bash
conda install -c conda-forge jupyterlab
```

Likewise, for Jupyter Notebook via `pip`:

```bash
pip install notebook
```

or via `conda`:

```bash
conda install -c conda-forge notebook
```

For additional information regarding the installation of [JupyterLab](https://jupyterlab.readthedocs.io/en/latest/getting_started/overview.html) or [Jupyter Notebook](https://jupyter-notebook.readthedocs.io/en/latest/), please refer to their respective documentation (see embedded links).
