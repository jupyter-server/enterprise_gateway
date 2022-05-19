This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster. It is built on [jupyter/scipy-notebook](https://hub.docker.com/r/jupyter/scipy-notebook/).

# What it Gives You

- IPython kernel support (with debugger)
- [Data science libraries](https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html#jupyter-scipy-notebook)

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a gateway-enabled Jupyter Notebook application against the Enterprise Gateway instance and pick the desired kernel to use in your notebook.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
