This image enables the use of an IRKernel kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster.  It is built on the base image [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r/), and adds [Apache Spark 2.4.1](https://spark.apache.org/docs/2.4.1/).  Note: The ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.

# What it Gives You
* IRkernel kernel support 
* Spark on kubernetes support from within a Jupyter Notebook

# Basic Use
Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).