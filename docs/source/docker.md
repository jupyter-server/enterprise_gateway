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
