This image enables the use of an IRKernel kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster.  It is currently built on [jupyter/r-notebook](https://hub.docker.com/r/jupyter/r-notebook/).

# What it Gives You
* IRKernel kernel support 

# Basic Use
Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).