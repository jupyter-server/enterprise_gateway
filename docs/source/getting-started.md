## Getting started

This document describes some of the basics of installing and running the
Jupyter Kernel Gateway.

#### Using pip

We make stable releases of the kernel gateway to PyPI. You can use `pip` to install the latest version along with its dependencies.

```bash
# install from pypi
pip install jupyter_kernel_gateway
```

Once installed, you can use the `jupyter` CLI to run the server.

```bash
# run it with default options
jupyter kernelgateway
```

#### Using jupyter/minimal-kernel

The [docker-stacks](https://github.com/jupyter/docker-stacks) project defines a [minimal-kernel](https://github.com/jupyter/docker-stacks/tree/master/minimal-kernel) Docker image. The Dockerfile for this image installs the kernel gateway and sets it as the default container command. You can run an instance of this container with the following commands:

```bash
docker pull jupyter/minimal-kernel
docker run -it --rm -p 8888:8888 jupyter/minimal-kernel
```

#### Using another docker-stacks image

You can add the kernel gateway to any [docker-stacks](https://github.com/jupyter/docker-stacks) image to get a more feature-filled kernel environment. For example, you could define a Dockerfile like so:

```bash
# start from the jupyter image with R, Python, and Scala (Apache Toree) kernels pre-installed
FROM jupyter/all-spark-notebook

# install the kernel gateway
RUN pip install jupyter_kernel_gateway

# run kernel gateway on container start, not notebook server
EXPOSE 8888
CMD ["jupyter", "kernelgateway", "--KernelGatewayApp.ip=0.0.0.0", "--KernelGatewayApp.port=8888"]
```

You can then build and run it.

```bash
docker build -t my/kernel-gateway .
docker run -it --rm -p 8888:8888 my/kernel-gateway
```
