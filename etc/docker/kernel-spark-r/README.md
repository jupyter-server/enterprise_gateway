This image enables the use of an IRKernel kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster.  It is currently built on [kubespark/spark-driver-r:v2.2.0-kubernetes-0.5.0](https://hub.docker.com/r/kubespark/spark-driver-r/) deriving from the [apache-spark-on-k8s](https://github.com/apache-spark-on-k8s/spark) fork.  As a result, the ability to issue `spark-submit` calls (used to launch spark-based kernels) within a Docker Swarm configuration probably won't yield the expected results.  We'll revisit this once Spark 2.4 is available.

# What it Gives You
* IRKernel kernel support 
* Spark on kubernetes support from within a Jupyter Notebook

# Basic Use
Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).