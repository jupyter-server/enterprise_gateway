This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster.  It is currently built on [kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0](https://hub.docker.com/r/kubespark/spark-driver-py/) deriving from the [apache-spark-on-k8s](https://github.com/apache-spark-on-k8s/spark) fork.  As a result, the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.  We'll revisit this once Spark 2.4 is available.

# What it Gives You
* IPython kernel support 
* Spark on kubernetes support from within a Jupyter Notebook

# Basic Use
Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
