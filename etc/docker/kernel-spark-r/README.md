This image enables the use of an IRKernel kernel launched from [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster. It is built on the base image [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r/), and adds [Apache Spark 2.4.6](https://spark.apache.org/docs/2.4.6/). Note: The ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.

# What it Gives You

- IRkernel kernel support
- Spark on kubernetes support from within a Jupyter Notebook

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a gateway-enabled Jupyter Notebook application against the Enterprise Gateway instance and pick the desired kernel to use in your notebook.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
