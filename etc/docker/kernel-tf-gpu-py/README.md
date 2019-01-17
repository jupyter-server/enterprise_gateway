This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster that can perform Tensorflow operations.  It is currently built on [tensorflow/tensorflow:1.12.0-gpu-py3](https://hub.docker.com/r/tensorflow/tensorflow/) deriving from the [tensorflow](https://github.com/tensorflow/tensorflow/blob/master/tensorflow/tools/docker/README.md) project.

# What it Gives You
* IPython kernel support supplemented with Tensorflow functionality

# Basic Use
Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
