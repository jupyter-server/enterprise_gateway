This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes cluster that can perform Tensorflow operations.  It is currently built on [tensorflow/tensorflow:1.9.0-gpu-py3](https://hub.docker.com/r/tensorflow/tensorflow/) deriving from the [tensorflow](https://github.com/tensorflow/tensorflow/blob/master/tensorflow/tools/docker/README.md) project.

# What it Gives You
* IPython kernel support supplemented with Tensorflow functionality

# Basic Use
Pull [elyra/kubernetes-enterprise-gateway](https://hub.docker.com/r/elyra/kubernetes-enterprise-gateway/), along with all of the elyra/kubernetes-kernel-* images to each of your kubernetes nodes.  Although manual seeding of images across the cluster is not required, it is highly recommended since kernel startup times can timeout and image downloads can seriously undermine that window.

Download the [kubernetes-enterprise-gateway.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/docker/kubernetes-enterprise-gateway/kubernetes-enterprise-gateway.yaml) file and make any necessary changes for your configuration.  We recommend that a persistent volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

Deploy Jupyter Enterprise Gateway using `kubectl apply -f kubernetes-enterprise-gateway.yaml`

Launch a Jupyter Notebook application using NB2KG (see [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) against  the Enterprise Gateway instance and pick either of the python-related kernels.

For more information, check our [repo](https://github.com/jupyter-incubator/enterprise_gateway) and [docs](http://jupyter-enterprise-gateway.readthedocs.io/en/latest/).
