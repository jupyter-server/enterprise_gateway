## Docker Images

The project produces three docker images to make both testing and general usage easier:
1. elyra/yarn-spark
1. elyra/enterprise-gateway
1. elyra/nb2kg

All images can be pulled from docker hub's [elyra organization](https://hub.docker.com/u/elyra/) and their 
docker files can be found in the github repository in the appropriate directory of 
[etc/docker](https://github.com/jupyter-incubator/enterprise_gateway/tree/master/etc/docker).

Local images can also be built via `make docker-images`.

### elyra/yarn-spark

The [elyra/yarn-spark](https://hub.docker.com/r/elyra/yarn-spark/) image is considered the base image 
upon which [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) is built.  It consist 
of a Hadoop (YARN) installation that includes Spark, Java, Anaconda and various kernel installations.

The tag of this image reflects the version of Spark included in the image and we don't anticipate the need to update this image regularly.

The primary use of this image is to quickly build elyra/enterprise-gateway images for testing and development
purposes.  To build a local image, run `make docker-image-yarn-spark`.  Note: the tag for this image will
still be `:2.1.0` since `elyra/enterprise-gateway` depends on this image/tag.

As of the 0.9.0 release, this image can be used to start a separate YARN cluster that, when combined with another
instance of elyra/enterprise-gateway can better demonstrate remote kernel functionality.

### elyra/enterprise-gateway

Image [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) is the primary image 
produced by this repository.  Built on [elyra/yarn-spark](https://hub.docker.com/r/elyra/yarn-spark/), it
also includes the various example kernelspecs contained in the repository.

By default, this container will start with enterprise gateway running as a service user named `elyra`.  This
user is enabled for `sudo` so that it can emulate other users where necessary.  Other users included in this 
image are `jovyan` (the user common in most Jupyter-based images, with UID=`1000` and GID=`100`), `bob` and 
`alice` (names commonly used in security-based examples).

We plan on producing one image per release to the 
[enterprise-gateway docker repo](https://hub.docker.com/r/elyra/enterprise-gateway/) where
the image's tag reflects the corresponding release.  Over time, we may integrate with docker hub to produce
this image on every build - where the commit hash becomes the tag.

To build a local image, run `make docker-image-enterprise-gateway`.  Because this is a development build, the
the tag for this image will be `:dev`.

### elyra/nb2kg

Image [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) is a simple image built 
on [jupyter/minimal-notebook](https://hub.docker.com/r/jupyter/minimal-notebook/) along with the latest
release of [NB2KG](https://github.com/jupyter-incubator/nb2kg).  The image 
also sets some of the new variables that pertain to enterprise gateway (e.g., `KG_REQUEST_TIMEOUT`, 
`KG_HTTP_USER`, `KERNEL_USERNAME`, etc.).

To build a local image, run `make docker-image-nb2kg`.  Because this is a development build, the 
tag for this image will be `:dev`.

## Kubernetes Images
The following sections describe the docker images used within Kubernetes environments - all of which can be pulled from 
the [Enterprise Gateway organization](https://hub.docker.com/r/elyra/) on dockerhub.

### elyra/kubernetes-enterprise-gateway
The primary image for Kubernetes support, [elyra/kubernetes-enterprise-gateway](https://hub.docker.com/r/elyra/kubernetes-enterprise-gateway/) 
contains the Enterprise Gateway server software and default kernelspec files.  Its deployment is completely a function 
of the [enterprise-gateway.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) file

We recommend that a persistent volume be used so that the kernelspec files can be accessed outside of the container
since we've found those to require post-deployment modifications from time to time.

### elyra/kubernetes-kernel-py
Image [elyra/kubernetes-kernel-py](https://hub.docker.com/r/elyra/kubernetes-kernel-py/) contains the IPython kernel.  It is currently built on the spark-on-kubernetes image 
(`kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0`) and can be launched 
as a spark application or in *vanilla* mode depending on its kernelspecs attributes.  We will likely introduce separate,
non-spark, containers based on anaconda - so each kernelspec will likely be associated with different images.

### elyra/kubernetes-kernel-tf-py
Image [elyra/kubernetes-kernel-tf-py](https://hub.docker.com/r/elyra/kubernetes-kernel-tf-py/) is built on the Tensorflow image (`tensorflow/tensorflow:1.9.0-py3`) and is solely a *vanilla* kernel in the 
sense that it does not support Spark context creation.  As noted in the image name, its language is Python and uses
the IPython kernel within.

### elyra/kubernetes-kernel-tf-gpu-py
Image [elyra/kubernetes-kernel-tf-gpu-py](https://hub.docker.com/r/elyra/kubernetes-kernel-tf-gpu-py/) is built on the Tensorflow image (`tensorflow/tensorflow:1.9.0-gpu-py3`) and, 
like its sibling image, does not support Spark context creation.  Unique to this image, on the other hand, is the fact that 
it can support GPUs.  As noted in the image name, its language is Python and uses
the IPython kernel within.

### elyra/kubernetes-kernel-scala
Image [elyra/kubernetes-kernel-scala](https://hub.docker.com/r/elyra/kubernetes-kernel-scala/) contains the Scala (Apache Toree) kernel and is currently build on the spark-on-kubernetes image (`kubespark/spark-driver:v2.2.0-kubernetes-0.5.0`).
Since Toree is currently tied to Spark, creation of a *vanilla* mode Scala kernel is not high on our current set of priorities.

### elyra/kubernetes-kernel-r
Image [elyra/kubernetes-kernel-r](https://hub.docker.com/r/elyra/kubernetes-kernel-r/) contains the IRKernel and is currently built on the spark-on-kubernetes image (`kubespark/spark-driver-r:v2.2.0-kubernetes-0.5.0`).
Like with `elyra/kubernetes-kernel-py` it can be launched in two modes depending on the need of a Spark context.