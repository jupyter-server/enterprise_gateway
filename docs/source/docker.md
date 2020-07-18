## Docker Images

The project produces three docker images to make both testing and general usage easier:
1. elyra/demo-base
1. elyra/enterprise-gateway-demo
1. elyra/nb2kg

All images can be pulled from docker hub's [elyra organization](https://hub.docker.com/u/elyra/) and their docker files can be found in the github repository in the appropriate directory of [etc/docker](https://github.com/jupyter/enterprise_gateway/tree/master/etc/docker).

Local images can also be built via `make docker-images`.

### elyra/demo-base

The [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/) image is considered the base image upon which [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) is built.  It consist of a Hadoop (YARN) installation that includes Spark, Java, miniconda and various kernel installations.

The primary use of this image is to quickly build elyra/enterprise-gateway images for testing and development purposes.  To build a local image, run `make demo-base`.

As of the 0.9.0 release, this image can be used to start a separate YARN cluster that, when combined with another instance of elyra/enterprise-gateway can better demonstrate remote kernel functionality.

### elyra/enterprise-gateway-demo

Built on [elyra/demo-base](https://hub.docker.com/r/elyra/demo-base/), [elyra/enterprise-gateway-demo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) also includes the various example kernelspecs contained in the repository.

By default, this container will start with enterprise gateway running as a service user named `jovyan`.  This user is enabled for `sudo` so that it can emulate other users where necessary.  Other users included in this image are `elyra`, `bob` and `alice` (names commonly used in security-based examples).

We plan on producing one image per release to the [enterprise-gateway-demo docker repo](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) where the image's tag reflects the corresponding release. 

To build a local image, run `make docker-image-enterprise-gateway-demo`.  Because this is a development build, the tag for this image will not reflect the value of the VERSION variable in the root Makefile but will be 'dev'.

### elyra/nb2kg

Image [elyra/nb2kg](https://hub.docker.com/r/elyra/nb2kg/) is a simple image built on [jupyterhub/k8s-singleuser-sample](https://hub.docker.com/r/https://hub.docker.com/r/jupyterhub/k8s-singleuser-sample/) along with the latest release of [NB2KG](https://github.com/jupyter/nb2kg).  The image also sets some of the new variables that pertain to enterprise gateway (e.g., `KG_REQUEST_TIMEOUT`, `KG_HTTP_USER`, `KERNEL_USERNAME`, etc.).

To build a local image, run `make docker-image-nb2kg`.  Because this is a development build, the tag for this image will not reflect the value of the VERSION variable in the root Makefile but will be 'dev'.

## Runtime Images

The following sections describe the docker images used within Kubernetes and Docker Swarm environments - all of which can be pulled from the [Enterprise Gateway organization](https://hub.docker.com/r/elyra/) on dockerhub.

### elyra/enterprise-gateway

The primary image for Kubernetes and Docker Swarm support, [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) contains the Enterprise Gateway server software and default kernelspec files.  For Kubernetes it is deployed using the [enterprise-gateway.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) file.  For Docker Swarm, deployment can be accomplished using [enterprise-gateway-swarm.sh](https://github.com/jupyter/enterprise_gateway/blob/master/etc/docker/enterprise-gateway-swarm.sh) although we should convert this to a docker compose yaml file at some point.

We recommend that a persistent/mounted volume be used so that the kernelspec files can be accessed outside of the container since we've found those to require post-deployment modifications from time to time.

### elyra/kernel-py

Image [elyra/kernel-py](https://hub.docker.com/r/elyra/kernel-py/) contains the IPython kernel.  It is currently built on the [jupyter/scipy-notebook](https://hub.docker.com/r/jupyter/scipy-notebook) image with additional support necessary for remote operation.

### elyra/kernel-spark-py

Image [elyra/kernel-spark-py](https://hub.docker.com/r/elyra/kernel-spark-py/) is built on [elyra/kernel-py](https://hub.docker.com/r/elyra/kernel-py) and includes the Spark 2.4 distribution for use in Kubernetes clusters. Please note that the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results. 

### elyra/kernel-tf-py

Image [elyra/kernel-tf-py](https://hub.docker.com/r/elyra/kernel-tf-py/) contains the IPython kernel.  It is currently built on the [jupyter/tensorflow-notebook](https://hub.docker.com/r/jupyter/tensorflow-notebook) image with additional support necessary for remote operation.

### elyra/kernel-scala

Image [elyra/kernel-scala](https://hub.docker.com/r/elyra/kernel-scala/) contains the Scala (Apache Toree) kernel and is built on [elyra/spark](https://hub.docker.com/r/elyra/spark) which is, itself, built using the scripts provided by the Spark 2.4 distribution for use in Kubernetes clusters. As a result, the ability to use the kernel within Spark within a Docker Swarm configuration probably won't yield the expected results. 

Since Toree is currently tied to Spark, creation of a *vanilla* mode Scala kernel is not high on our current set of priorities.

### elyra/kernel-r

Image [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r/) contains the IRKernel and is currently built on the [jupyter/r-notebook](https://hub.docker.com/r/jupyter/r-notebook/) image.

### elyra/kernel-spark-r

Image [elyra/kernel-spark-r](https://hub.docker.com/r/elyra/kernel-spark-r/) also contains the IRKernel but is built on [elyra/kernel-r](https://hub.docker.com/r/elyra/kernel-r) and includes the Spark 2.4 distribution for use in Kubernetes clusters.

## Custom Kernel Images

This section presents information needed for how a custom kernel image could be built for your own uses with Enterprise Gateway.  This is typically necessary if one desires to extend the existing image with additional supporting libraries or an image that encapsulates a different set of functionality altogether.

### Extending Existing Kernel Images

A common form of customization occurs when the existing kernel image is serving the fundamentals but the user wishes it be extended with additional libraries so as to prevent the need of their imports within the Notebook interactions.  Since the image already meets the [basic requirements](docker.html#requirements-for-custom-kernel-images), this is really just a matter of referencing the existing image in the `FROM` statement and installing additional libraries.  Because the EG kernel images do not run as the `root` user, you may need to switch users to perform the update.

```dockerfile
FROM elyra/kernel-py:VERSION

USER root  # switch to root user to perform installation (if necessary)

RUN pip install my-libraries

USER $NB_UID  # switch back to the jovyan user 
```

### Bringing Your Own Kernel Image

Users that do not wish to extend an existing kernel image must be cognizant of a couple things.
1. Requirements of a kernel-based image to be used by Enterprise Gateway.
2. Is the base image one from [Jupyter Docker-stacks](https://github.com/jupyter/docker-stacks)?

#### Requirements for Custom Kernel Images
Custom kernel images require some support files from the Enterprise Gateway repository.  These are packaged into a tar file for each release starting in `2.2.0rc2`.  This tar file (named `jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz`) is composed of a few files - one bootstrap script and a kernel launcher (one per kernel type).

##### Bootstrap-kernel.sh
Enterprise Gateway provides a single [bootstrap-kernel.sh](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kernel-launchers/bootstrap/bootstrap-kernel.sh) script that handles the three kernel languages supported out of the box - Python, R, and Scala.  When a kernel image is started by Enterprise Gateway, parameters used within the bootstrap-kernel.sh script are conveyed via environment variables.  The bootstrap script is then responsible for validating and converting those parameters to meaningful arguments to the appropriate launcher.

##### Kernel Launcher
The kernel launcher, as discussed [here](system-architecture.html#kernel-launchers) does a number of things.  In paricular, it creates the connection ports and conveys that connection information back to Enterprise Gateway via the socket identified by the response address parameter.  Although not a requirement for container-based usage, it is recommended that the launcher be written in the same language as the kernel.  (This is more of a requirement when used in applications like YARN.)

#### About Jupyter Docker-stacks Images
Most of what is presented assumes the base image for your custom image is derived from the [Jupyter Docker-stacks](https://github.com/jupyter/docker-stacks) repository.  As a result, it's good to cover what makes up those assumptions so you can build your own image independently from the docker-stacks repository.

All of the images produced from the docker-stacks repository come with a certain user configured.  This user is named `jovyan` and is mapped to a user id (UID) of `1000` and a group id (GID) of `100` - named `users`.

The various startup scripts and commands typically reside in `/usr/local/bin` and we recommend trying to adhere to that policy. 

The base jupyter image, upon which most all images from docker-stacks are built, also contains a `fix-permissions` script that is responsible for _gracefully_ adjusting permissions based on its given parameters.  By only changing the necessary permissions, use of this script minimizes the size of the docker layer in which that command is invoked durnig the build of the docker image.

#### Sample Dockerfiles for Custom Kernel Images
Below we provide two working Dockerfiles that produce custom kernel images.  One based on an existing image from Jupyter docker-stacks, the other from an independent base image.

##### Custom Kernel Image Built on Jupyter Image
Here's an example Dockerfile that installs the minimally necessary items for a python-based kernel image built on the docker-stack image `jupyter/scipy-notebook`.  Note: the string `VERSION` must be replaced with the appropriate value.

```dockerfile
# Choose a base image.  Preferrably one from https://github.com/jupyter/docker-stacks
FROM jupyter/scipy-notebook:61d8aaedaeaf
 
# Switch user to root since, if from docker-stacks, its probably jovyan
USER root
 
# Install any packages required for the kernel-wrapper.  If the image
# does not contain the target kernel (i.e., IPython, IRkernel, etc.,
# it should be installed as well.
RUN pip install pycrypto

# Download and extract the enterprise gateway kernel launchers and bootstrap 
# files and deploy to /usr/local/bin. Change permissions to NB_UID:NB_GID.
RUN wget https://github.com/jupyter/enterprise_gateway/releases/download/vVERSION/jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz &&\
        tar -xvf jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz -C /usr/local/bin &&\
        rm -f jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz &&\
        fix-permissions /usr/local/bin

# Switch user back to jovyan and setup language and default CMD
USER $NB_UID
ENV KERNEL_LANGUAGE python
CMD /usr/local/bin/bootstrap-kernel.sh
```

##### Independent Custom Kernel Image
If your base image is not from docker-stacks, it is recommended that you NOT run the image as USER `root` and create an _image user_ that is not UID 0.  For this example, we will create the `jovyan` user with UID `1000` and a primary group of `users`, GID `100`.  Note that Enterprise Gateway makes no assumption relative to the user in which the kernel image is running.

Aside from configuring the image user, all other aspects of customization are the same.  In this case, we'll use the tensorflow-gpu image and convert it to be usable via Enterprise Gateway as a custom kernel image.  Note that because this image didn't have `wget` we used `curl` to download the supporting kernel-image files.

```dockerfile
FROM tensorflow/tensorflow:1.12.0-gpu-py3

USER root

# Install OS dependencies required for the kernel-wrapper. Missing
# packages can be installed later only if container is running as
# privileged user.
RUN apt-get update && apt-get install -yq --no-install-recommands \
    build-essential \
    libsm6 \
    libxext-dev \
    libxrender1 \
    netcat \
    python3-dev \
    tzdata \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install any packages required for the kernel-wrapper.  If the image
# does not contain the target kernel (i.e., IPython, IRkernel, etc.,
# it should be installed as well.
RUN pip install pycrypto

# Download and extract the enterprise gateway kernel launchers and bootstrap
# files and deploy to /usr/local/bin. Change permissions to NB_UID:NB_GID.
RUN curl -L https://github.com/jupyter/enterprise_gateway/releases/download/vVERSION/jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz | \
    tar -xz -C /usr/local/bin 

RUN adduser --system --uid 1000 --gid 100 jovyan && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
    chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers

ENV NB_UID 1000
ENV NB_GID 100
USER jovyan
ENV KERNEL_LANGUAGE python
CMD /usr/local/bin/bootstrap-kernel.sh
```

### Deploying Your Custom Kernel Image
The final step in deploying a customer kernel image is creating a corresponding kernelspec directory that is avaiable to Enterprise Gateway.  Since Enterprise Gateway is also running in a container, its import that its kernelspecs folder either be mounted externally or a new EG image is created with the appropriate kernelspecs directory in place.  For the purposes of this discussion, we'll assume the kernelspecs directory, `/usr/local/share/jupyter/kernels` is externally mounted.

- Find a similar kernelspec directory from which to create your custom kernelspec.  The most important aspect to this is matching the language of your kernel since it will use the same [kernel launcher](docker.html#kernel-launcher).  Another important question is whether or not your custom kernel uses Spark, because those kernelspecs will vary significantly since many of the spark options reside in the kernel.json's `env` stanza.  Since our examples use _vanilla_ (non-Spark) python kernels we'll use the `python_kubernetes` kernelspec as our basis.
```bash
cd /usr/local/share/jupyter/kernels
cp -r python_kubernetes python_myCustomKernel
```

- Edit the `kernel.json` file and change the `display_name:`, `image_name:` and path to `launch_kubernetes.py` script.
```json
{
  "language": "python",
  "display_name": "My Custom Kernel",
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy",
      "config": {
        "image_name": "myDockerHub/myCustomKernelImage:myTag"
      }
    }
  },
  "env": {
  },
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_myCustomKernel/scripts/launch_kubernetes.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
}
```
- If using a whitelist (`EG_KERNEL_WHITELIST`), be sure to update it with the new kernelspec directory name (e.g., `python_myCustomKernel`) and restart/redeploy Enterprise Gateway.  
- Launch or refresh your Notebook session and confirm `My Custom Kernel` appears in the _new kernel_ drop-down.
- Create a new notebook using `My Custom Kernel`.
