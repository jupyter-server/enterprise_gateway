## Docker Images

The project produces three docker images to make both testing and general usage easier:
1. elyra/yarn-spark
1. elyra/enterprise-gateway-demo
1. elyra/nb2kg

All images can be pulled from docker hub's [elyra organization](https://hub.docker.com/u/elyra/) and their 
docker files can be found in the github repository in the appropriate directory of 
[etc/docker](https://github.com/jupyter/enterprise_gateway/tree/master/etc/docker).

Local images can also be built via `make docker-images`.

### elyra/yarn-spark

The [elyra/yarn-spark](https://hub.docker.com/r/elyra/yarn-spark/) image is considered the base image 
upon which [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) is built.  It consist 
of a Hadoop (YARN) installation that includes Spark, Java, Anaconda and various kernel installations.

The tag of this image reflects the version of Spark included in the image and we don't anticipate the need to update this image regularly.

The primary use of this image is to quickly build elyra/enterprise-gateway images for testing and development
purposes.  To build a local image, run `make docker-image-yarn-spark`.

As of the 0.9.0 release, this image can be used to start a separate YARN cluster that, when combined with another
instance of elyra/enterprise-gateway can better demonstrate remote kernel functionality.

### elyra/enterprise-gateway-demo

Image [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) is the primary image 
produced by this repository.  Built on [elyra/yarn-spark](https://hub.docker.com/r/elyra/yarn-spark/), it
also includes the various example kernelspecs contained in the repository.

By default, this container will start with enterprise gateway running as a service user named `elyra`.  This
user is enabled for `sudo` so that it can emulate other users where necessary.  Other users included in this 
image are `jovyan` (the user common in most Jupyter-based images, with UID=`1000` and GID=`100`), `bob` and 
`alice` (names commonly used in security-based examples).

We plan on producing one image per release to the 
[enterprise-gateway-demo docker repo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) where
the image's tag reflects the corresponding release.  Over time, we may integrate with docker hub to produce
this image on every build - where the commit hash becomes the tag.

To build a local image, run `make docker-image-enterprise-gateway-demo`.  Because this is a development build, the
tag for this image will be what is set as VERSION (e.g. 2.0.0.dev0) in the root Makefile.

### elyra/nb2kg

Image [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) is a simple image built 
on [jupyter/minimal-notebook](https://hub.docker.com/r/jupyter/minimal-notebook/) along with the latest
release of [NB2KG](https://github.com/jupyter/nb2kg).  The image 
also sets some of the new variables that pertain to enterprise gateway (e.g., `KG_REQUEST_TIMEOUT`, 
`KG_HTTP_USER`, `KERNEL_USERNAME`, etc.).

To build a local image, run `make docker-image-nb2kg`.  Because this is a development build, the 
tag for this image will be what VERSION (e.g. 2.0.0.dev0) is set to in the root Makefile.

## Runtime Images
The following sections describe the docker images used within Kubernetes and Docker Swarm environments - all of which can be pulled from 
the [Enterprise Gateway organization](https://hub.docker.com/r/elyra/) on dockerhub.

### elyra/enterprise-gateway
The primary image for Kubernetes and Docker Swarm support, [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) 
contains the Enterprise Gateway server software and default kernelspec files.  For Kubernetes it is deployed using the [enterprise-gateway.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) file.  For Docker Swarm, deployment can be accomplished using [enterprise-gateway-swarm.sh](https://github.com/jupyter/enterprise_gateway/blob/master/etc/docker/enterprise-gateway-swarm.sh) although we should convert this to a docker compose yaml file at some point.

We recommend that a persistent/mounted volume be used so that the kernelspec files can be accessed outside of the container
since we've found those to require post-deployment modifications from time to time.

### elyra/kernel-py
Image [elyra/kernel-py](https://hub.docker.com/r/elyra/kernel-py/) contains the IPython kernel.  It is currently built on the spark-on-kubernetes image 
(`kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0`) and can be launched 
as a spark application or in *vanilla* mode depending on its kernelspecs attributes. Please note that the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.  We'll revisit this once Spark 2.4 is available. We will likely introduce separate,
non-spark, containers based on anaconda - so each kernelspec will likely be associated with different images.

### elyra/kernel-tf-py
Image [elyra/kernel-tf-py](https://hub.docker.com/r/elyra/kernel-tf-py/) is built on the Tensorflow image (`tensorflow/tensorflow:1.9.0-py3`) and is solely a *vanilla* kernel in the 
sense that it does not support Spark context creation.  As noted in the image name, its language is Python and uses
the IPython kernel within.

### elyra/kernel-tf-gpu-py
Image [elyra/kernel-tf-gpu-py](https://hub.docker.com/r/elyra/kernel-tf-gpu-py/) is built on the Tensorflow image (`tensorflow/tensorflow:1.9.0-gpu-py3`) and, 
like its sibling image, does not support Spark context creation.  Unique to this image, on the other hand, is the fact that 
it can support GPUs.  As noted in the image name, its language is Python and uses
the IPython kernel within.

### elyra/kernel-scala
Image [elyra/kernel-scala](https://hub.docker.com/r/elyra/kernel-scala/) contains the Scala (Apache Toree) kernel and is currently build on the spark-on-kubernetes image (`kubespark/spark-driver:v2.2.0-kubernetes-0.5.0`). As a result, the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.  We'll revisit this once Spark 2.4 is available.

Since Toree is currently tied to Spark, creation of a *vanilla* mode Scala kernel is not high on our current set of priorities.

### elyra/kernel-r
Image [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r/) contains the IRKernel and is currently built on the [jupyter/r-notebook/](https://hub.docker.com/r/jupyter/r-notebook/) image.

### elyra/kernel-spark-r
Image [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r/) contains the IRKernel and is currently built on the spark-on-kubernetes image (`kubespark/spark-driver-r:v2.2.0-kubernetes-0.5.0`).  As a result, the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results.  We'll revisit this once Spark 2.4 is available.
