This image adds support for [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster.  It is currently built on [kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0]() deriving from the [apache-spark-on-k8s](https://github.com/apache-spark-on-k8s/spark) fork.  As a result, the ability to issue `spark-submit` calls (used to launch spark-based kernels) within a Docker Swarm configuration probably won't yield the expected results.  We'll revisit this once Spark 2.4 is available.

**Note: If you're looking for the YARN-based image of this name, it has been moved to [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/).**

# What it Gives You
* [Jupyter Enterprise Gateway](https://github.com/jupyter/enterprise_gateway)
* Python/R/Toree kernels that can be launched and distributed across a managed cluster.

# Basic Use
Pull this image, along with all of the elyra/kernel-* images to each of your managed nodes.  Although manual seeding of images across the cluster is not required, it is highly recommended since kernel startup times can timeout and image downloads can seriously undermine that window.

## Kubernetes
Download the [enterprise-gateway.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) file and make any necessary changes for your configuration.  We recommend that a persistent volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

Deploy Jupyter Enterprise Gateway using `kubectl apply -f enterprise-gateway.yaml`

## Docker Swarm
Download the [enterprise-gateway-swarm.sh](https://github.com/jupyter/enterprise_gateway/blob/master/etc/docker/enterprise-gateway-swarm.sh) file and make any necessary changes for your configuration.  We recommend that a volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

## Docker (Traditional)
Same instructions as for Docker Swarm although we've provided [enterprise-gateway-docker.sh](https://github.com/jupyter/enterprise_gateway/blob/master/etc/docker/enterprise-gateway-docker.sh) for download.  Please note that you can still run Enterprise Gateway as a traditional docker container within a Docker Swarm cluster, yet have the kernel containers launched as Docker Swarm services since how the kernels are launched is a function of their configured process proxy class.

For more information, check our [repo](https://github.com/jupyter/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
