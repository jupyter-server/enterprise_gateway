This image enables the use of a Scala ([Apache Toree](http://toree.apache.org/)) kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster.  It is built on [elyra/spark:v2.4.1](https://hub.docker.com/r/elyra/spark/) deriving from the [Apache Spark 2.4.1 release](https://spark.apache.org/docs/2.4.1/).  Note: The ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.

# What it Gives You
* Scala (Toree) kernel support 
* Spark on kubernetes support from within a Jupyter Notebook

# Basic Use
Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
