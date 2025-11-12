# Custom Kernel Images

This section presents information needed for how a custom kernel image could be built for your own uses with Enterprise Gateway. This is typically necessary if one desires to extend the existing image with additional supporting libraries or an image that encapsulates a different set of functionality altogether.

## Extending Existing Kernel Images

A common form of customization occurs when the existing kernel image is serving the fundamentals but the user wishes it be extended with additional libraries to prevent the need of their imports within the Notebook interactions. Since the image already meets the [basic requirements](#requirements-for-custom-kernel-images), this is really just a matter of referencing the existing image in the `FROM` statement and installing additional libraries. Because the EG kernel images do not run as the `root` user, you may need to switch users to perform the update.

```dockerfile
FROM elyra/kernel-py:VERSION

USER root  # switch to root user to perform installation (if necessary)

RUN pip install my-libraries

USER $NB_UID  # switch back to the jovyan user
```

## Bringing Your Own Kernel Image

Users that do not wish to extend an existing kernel image must be cognizant of a couple of things.

1. Requirements of a kernel-based image to be used by Enterprise Gateway.
1. Is the base image one from [Jupyter Docker-stacks](https://github.com/jupyter/docker-stacks)?

### Requirements for Custom Kernel Images

Custom kernel images require some support files from the Enterprise Gateway repository. These are packaged into a tar file for each release starting in `2.5.0`. This tar file (named `jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz`) is composed of a few files - one bootstrap script and a kernel launcher (one per kernel type).

#### Bootstrap-kernel.sh

Enterprise Gateway provides a single [bootstrap-kernel.sh](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/bootstrap/bootstrap-kernel.sh) script that handles the three kernel languages supported out of the box - Python, R, and Scala. When a kernel image is started by Enterprise Gateway, parameters used within the bootstrap-kernel.sh script are conveyed via environment variables. The bootstrap script is then responsible for validating and converting those parameters to meaningful arguments to the appropriate launcher.

#### Kernel Launcher

The kernel launcher, as discussed [here](kernel-launcher.md) does a number of things. In particular, it creates the connection ports and conveys that connection information back to Enterprise Gateway via the socket identified by the response address parameter. Although not a requirement for container-based usage, it is recommended that the launcher be written in the same language as the kernel. (This is more of a requirement when used in applications like Hadoop YARN.)

### About Jupyter Docker-stacks Images

Most of what is presented assumes the base image for your custom image is derived from the [Jupyter Docker-stacks](https://github.com/jupyter/docker-stacks) repository. As a result, it's good to cover what makes up those assumptions so you can build your own image independently of the docker-stacks repository.

All images produced from the docker-stacks repository come with a certain user configured. This user is named `jovyan` and is mapped to a user id (UID) of `1000` and a group id (GID) of `100` - named `users`.

The various startup scripts and commands typically reside in `/usr/local/bin` and we recommend trying to adhere to that policy.

The base jupyter image, upon which most all images from docker-stacks are built, also contains a `fix-permissions` script that is responsible for _gracefully_ adjusting permissions based on its given parameters. By only changing the necessary permissions, use of this script minimizes the size of the docker layer in which that command is invoked during the build of the docker image.

### Sample Dockerfiles for Custom Kernel Images

Below we provide two working Dockerfiles that produce custom kernel images. One based on an existing image from Jupyter docker-stacks, the other from an independent base image.

#### Custom Kernel Image Built on Jupyter Image

Here's an example Dockerfile that installs the minimally necessary items for a Python-based kernel image built on the docker-stack image `jupyter/scipy-notebook`. Note: the string `VERSION` must be replaced with the appropriate value.

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
RUN wget https://github.com/jupyter-server/enterprise_gateway/releases/download/vVERSION/jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz &&\
        tar -xvf jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz -C /usr/local/bin &&\
        rm -f jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz &&\
        fix-permissions /usr/local/bin

# Switch user back to jovyan and setup language and default CMD
USER $NB_UID
ENV KERNEL_LANGUAGE python
CMD /usr/local/bin/bootstrap-kernel.sh
```

#### Independent Custom Kernel Image

If your base image is not from docker-stacks, it is recommended that you NOT run the image as USER `root` and create an _image user_ that is not UID 0. For this example, we will create the `jovyan` user with UID `1000` and a primary group of `users`, GID `100`. Note that Enterprise Gateway makes no assumption relative to the user in which the kernel image is running.

Aside from configuring the image user, all other aspects of customization are the same. In this case, we'll use the tensorflow-gpu image and convert it to be usable via Enterprise Gateway as a custom kernel image. Note that because this image didn't have `wget` we used `curl` to download the supporting kernel-image files.

```dockerfile
FROM tensorflow/tensorflow:2.5.0-gpu-jupyter

USER root

# Install OS dependencies required for the kernel-wrapper. Missing
# packages can be installed later only if container is running as
# privileged user.
RUN apt-get update && apt-get install -yq --no-install-recommends \
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
RUN curl -L https://github.com/jupyter-server/enterprise_gateway/releases/download/vVERSION/jupyter_enterprise_gateway_kernel_image_files-VERSION.tar.gz | \
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

## Deploying Your Custom Kernel Image

The final step in deploying a customer kernel image is creating a corresponding kernel specifications directory that is available to Enterprise Gateway. Since Enterprise Gateway is also running in a container, its import that its kernel specifications directory either be mounted externally or a new Enterprise Gateway image is created with the appropriate directory in place. For the purposes of this discussion, we'll assume the kernel specifications directory, `/usr/local/share/jupyter/kernels`, is externally mounted.

- Find a similar kernel specification directory from which to create your custom kernel specification. The most important aspect to this is matching the language of your kernel since it will use the same [kernel launcher](#kernel-launcher). Another important question is whether your custom kernel uses Spark, because those kernel specifications will vary significantly since many of the spark options reside in the `kernel.json`'s `env` stanza. Since our examples use _vanilla_ (non-Spark) python kernels we'll use the `python_kubernetes` kernel specification as our basis.

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
  "env": {},
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_myCustomKernel/scripts/launch_kubernetes.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```

- If using kernel filtering (`EG_ALLOWED_KERNELS`), be sure to update it with the new kernel specification directory name (e.g., `python_myCustomKernel`) and restart/redeploy Enterprise Gateway.
- Launch or refresh your Notebook session and confirm `My Custom Kernel` appears in the _new kernel_ drop-down.
- Create a new notebook using `My Custom Kernel`.
