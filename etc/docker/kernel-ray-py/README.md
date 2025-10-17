This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster. It is built on the base image [rayproject/ray:2.50.0.714bc0-extra-py311-cpu](https://hub.docker.com/r/rayproject/ray/), and provides [Ray 2.50.0](https://docs.ray.io/) for distributed Python computing.

# What it Gives You

- IPython kernel support (with debugger)
- Ray 2.50.0 for distributed computing
- Python 3.11 environment
- Ray on Kubernetes support from within a Jupyter Notebook

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a gateway-enabled Jupyter Notebook application against the Enterprise Gateway instance and pick the Ray kernel to use in your notebook.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
