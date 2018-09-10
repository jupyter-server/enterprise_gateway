This image adds support for [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster.  It is currently built on [kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0]() deriving from the [apache-spark-on-k8s](https://github.com/apache-spark-on-k8s/spark) fork.

**Note: If you're looking for the YARN-based image of this name, it has been moved to [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/).**

# What it Gives You
* [Jupyter Enterprise Gateway](https://github.com/jupyter-incubator/enterprise_gateway)
* Python/R/Toree kernels that can be launched and distributed across a Kubernetes cluster.

# Basic Use
Pull this image, along with all of the elyra/kernel-* images to each of your kubernetes nodes.  Although manual seeding of images across the cluster is not required, it is highly recommended since kernel startup times can timeout and image downloads can seriously undermine that window.

Download the [enterprise-gateway.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) file and make any necessary changes for your configuration.  We recommend that a persistent volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

Deploy Jupyter Enterprise Gateway using `kubectl apply -f enterprise-gateway.yaml`

For more information, check our [repo](https://github.com/jupyter-incubator/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
