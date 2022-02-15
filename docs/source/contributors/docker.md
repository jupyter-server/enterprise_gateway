# Docker Images

All docker images can be pulled from docker hub's [elyra organization](https://hub.docker.com/u/elyra/) and their docker files can be found in the github repository in the appropriate directory of [etc/docker](https://github.com/jupyter-server/enterprise_gateway/tree/master/etc/docker).

Local images can also be built via `make docker-images`.

The following sections describe the docker images used within Kubernetes and Docker Swarm environments - all of which can be pulled from the [Enterprise Gateway organization](https://hub.docker.com/r/elyra/) on dockerhub.

## elyra/enterprise-gateway

The primary image for Kubernetes and Docker Swarm support, [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) contains the Enterprise Gateway server software and default kernelspec files.  For Kubernetes it is deployed using the [enterprise-gateway.yaml](https://github.com/jupyter-server/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) file.  For Docker Swarm, deployment can be accomplished using [enterprise-gateway-swarm.sh](https://github.com/jupyter-server/enterprise_gateway/blob/master/etc/docker/enterprise-gateway-swarm.sh) although we should convert this to a docker compose yaml file at some point.

We recommend that a persistent/mounted volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

## elyra/kernel-py

Image [elyra/kernel-py](https://hub.docker.com/r/elyra/kernel-py/) contains the IPython kernel.  It is currently built on the [jupyter/scipy-notebook](https://hub.docker.com/r/jupyter/scipy-notebook) image with additional support necessary for remote operation.

## elyra/kernel-spark-py

Image [elyra/kernel-spark-py](https://hub.docker.com/r/elyra/kernel-spark-py/) is built on [elyra/kernel-py](https://hub.docker.com/r/elyra/kernel-py) and includes the Spark 2.4 distribution for use in Kubernetes clusters. Please note that the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results. 

## elyra/kernel-tf-py

Image [elyra/kernel-tf-py](https://hub.docker.com/r/elyra/kernel-tf-py/) contains the IPython kernel.  It is currently built on the [jupyter/tensorflow-notebook](https://hub.docker.com/r/jupyter/tensorflow-notebook) image with additional support necessary for remote operation.

## elyra/kernel-scala

Image [elyra/kernel-scala](https://hub.docker.com/r/elyra/kernel-scala/) contains the Scala (Apache Toree) kernel and is built on [elyra/spark](https://hub.docker.com/r/elyra/spark) which is, itself, built using the scripts provided by the Spark 2.4 distribution for use in Kubernetes clusters. As a result, the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results. 

Since Toree is currently tied to Spark, creation of a *vanilla* mode Scala kernel is not high on our current set of priorities.

## elyra/kernel-r

Image [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r/) contains the IRKernel and is currently built on the [jupyter/r-notebook](https://hub.docker.com/r/jupyter/r-notebook/) image.

## elyra/kernel-spark-r

Image [elyra/kernel-spark-r](https://hub.docker.com/r/elyra/kernel-spark-r/) also contains the IRKernel but is built on [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r) and includes the Spark 2.4 distribution for use in Kubernetes clusters.


## Ancillary Docker Images

The project produces two docker images to make testing easier: [elyra/demo-base](docker.html#elyra-demo-base) and [elyra/enterprise-gateway-demo](docker.html#elyra-enterprise-gateway-demo).

### elyra/demo-base

The [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/) image is considered the base image upon which [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) is built.  It consist of a Hadoop (YARN) installation that includes Spark, Java, miniconda and various kernel installations.

The primary use of this image is to quickly build elyra/enterprise-gateway images for testing and development purposes.  To build a local image, run `make demo-base`.

As of the 0.9.0 release, this image can be used to start a separate YARN cluster that, when combined with another instance of elyra/enterprise-gateway can better demonstrate remote kernel functionality.

### elyra/enterprise-gateway-demo

Built on [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/), [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) also includes the various example kernelspecs contained in the repository.

By default, this container will start with enterprise gateway running as a service user named `jovyan`.  This user is enabled for `sudo` so that it can emulate other users where necessary.  Other users included in this image are `elyra`, `bob` and `alice` (names commonly used in security-based examples).

We plan on producing one image per release to the [enterprise-gateway-demo docker repo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) where the image's tag reflects the corresponding release. 

To build a local image, run `make docker-image-enterprise-gateway-demo`.  Because this is a development build, the tag for this image will not reflect the value of the VERSION variable in the root Makefile but will be 'dev'.
