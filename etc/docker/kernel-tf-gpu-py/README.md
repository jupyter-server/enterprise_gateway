This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster that can perform Tensorflow operations. It is currently built on [tensorflow/tensorflow:2.7.0-gpu-jupyter](https://hub.docker.com/r/tensorflow/tensorflow/) deriving from the [tensorflow](https://github.com/tensorflow/tensorflow) project.

# What it Gives You

- IPython kernel support supplemented with Tensorflow functionality (and debugger)

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a gateway-enabled Jupyter Notebook application against the Enterprise Gateway instance and pick the desired kernel to use in your notebook.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
