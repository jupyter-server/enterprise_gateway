## Getting started

This document describes some of the basics of installing and configuring
Jupyter Kernel Gateway.

### Installation

The Jupyter Kernel Gateway can be installed using `pip`.

```bash
# install from pypi
pip install jupyter_kernel_gateway
```

As an alternative to installing the kernel gateway from pypi, one can also
use the [minimal-kernel](https://hub.docker.com/r/jupyter/minimal-kernel/) 
image from the [docker-stacks](https://github.com/jupyter/docker-stacks)
project to try out its functionalities.  

Additional information about using Docker with Jupyter Kernel Gateway is
found in the [Developer Installation](devinstall.md) section.

### Try It

These command allow you to quickly configure and run the kernel gateway:

```bash
# show all config options
jupyter kernelgateway --help-all

# run it with default options
jupyter kernelgateway
```

