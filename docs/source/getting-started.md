## Getting started

This document describes some of the basics of installing and running the
Jupyter Kernel Gateway.

### Using pip

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

### Using conda

You can install the kernel gateway using conda as well.

```bash
conda install -c conda-forge jupyter_kernel_gateway
```

Once installed, you can use the `jupyter` CLI to run the server as shown above.

### Using a docker-stacks image

You can add the kernel gateway to any [docker-stacks](https://github.com/jupyter/docker-stacks) image by writing a Dockerfile patterned after the following example:

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
