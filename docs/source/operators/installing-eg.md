# Installing Enterprise Gateway (common)

For new users, we **highly recommend** [installing Anaconda](https://www.anaconda.com/download).
Anaconda conveniently installs Python, the [Jupyter Notebook](https://jupyter.readthedocs.io/en/latest/install.html), the [IPython kernel](http://ipython.readthedocs.io/en/stable/install/kernel_install.html) and other commonly used
packages for scientific computing and data science.

Use the following installation steps:

- Download [Anaconda](https://www.anaconda.com/download). We recommend downloading Anaconda’s
  latest Python version (currently Python 3.9).

- Install the version of Anaconda which you downloaded, following the instructions on the download page.

- Install the latest version of Jupyter Enterprise Gateway from [PyPI](https://pypi.python.org/pypi/jupyter_enterprise_gateway/)
  or [conda forge](https://conda-forge.org/) along with its dependencies.

```{warning}
Enterprise Gateway is currently incompatible with `jupyter_client >= 7.0`.  As a result, you should **not** install Enterprise Gateway into the same Python environment in which you intend to run Jupyter Notebook or Jupyter Lab since they will likely be using `jupyter_client >= 7.0`.  Since Enterprise Gateway is tupically installed on servers remote from the notebook users, this is usually not an issue.
```

```bash
# install using pip from pypi
pip install --upgrade jupyter_enterprise_gateway
```

```bash
# install using conda from conda forge
conda install -c conda-forge jupyter_enterprise_gateway
```

At this point, the Jupyter Enterprise Gateway deployment provides local kernel support which is fully compatible with Jupyter Kernel Gateway.

To uninstall Jupyter Enterprise Gateway...

```bash
#uninstall using pip
pip uninstall jupyter_enterprise_gateway
```

```bash
#uninstall using conda
conda uninstall jupyter_enterprise_gateway
```
