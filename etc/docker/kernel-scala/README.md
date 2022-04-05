This image enables the use of a Scala ([Apache Toree](https://toree.apache.org/)) kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster. It is built on [elyra/spark:v2.4.6](https://hub.docker.com/r/elyra/spark/) deriving from the [Apache Spark 2.4.6 release](https://spark.apache.org/docs/2.4.6/). Note: The ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.

# What it Gives You

- Scala (Toree) kernel support
- Spark on kubernetes support from within a Jupyter Notebook

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a gateway-enabled Jupyter Notebook application against the Enterprise Gateway instance and pick the desired kernel to use in your notebook.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
