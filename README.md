# Jupyter Kernel Gateway

[![Google Group](https://img.shields.io/badge/-Google%20Group-lightgrey.svg)](https://groups.google.com/forum/#!forum/jupyter) 
[![PyPI version](https://badge.fury.io/py/jupyter_kernel_gateway.svg)](https://badge.fury.io/py/jupyter_kernel_gateway) 
[![Build Status](https://travis-ci.org/jupyter-incubator/dashboards.svg?branch=master)](https://travis-ci.org/jupyter/kernel_gateway)
[![Code Health](https://landscape.io/github/jupyter/kernel_gateway/master/landscape.svg?style=flat)](https://landscape.io/github/jupyter/kernel_gateway/master)
[![Documentation Status](http://readthedocs.org/projects/jupyter-kernel-gateway/badge/?version=latest)](https://jupyter-kernel-gateway.readthedocs.io/en/latest/?badge=latest)

## Overview

The kernel gateway is a web server that supports different mechanisms for spawning and
communicating with Jupyter kernels, such as:

* A Jupyter Notebook server-compatible HTTP API used for requesting kernels
  and talking the [Jupyter kernel protocol](https://jupyter-client.readthedocs.io/en/latest/messaging.html)
  with the kernels over Websockets
* A HTTP API defined by annotated notebook cells that maps HTTP verbs and
  resources to code to execute on a kernel

The server launches kernels in its local process/filesystem space. It can be containerized and scaled out using common technologies like [tmpnb](https://github.com/jupyter/tmpnb), [Cloud Foundry](https://github.com/cloudfoundry), and [Kubernetes](http://kubernetes.io/).

### Example Uses of Kernel Gateway

* Attach a local Jupyter Notebook server to a compute cluster in the cloud running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use kernels (e.g., web dashboards using [jupyter-js-services](https://github.com/jupyter/jupyter-js-services))
* Create microservices from notebooks using the Kernel Gateway [`notebook-http` mode](https://jupyter-kernel-gateway.readthedocs.io/en/latest/http-mode.html)

### Features

See the [Features page](https://jupyter-kernel-gateway.readthedocs.io/en/latest/features.html) in the 
documentation for a list of the Jupyter Kernel Gateway features.

## Installation

Detailed installation instructions are located in the 
[Getting Started page](https://jupyter-kernel-gateway.readthedocs.io/en/latest/getting-started.html)
of the project docs. Here's a quick start using `pip`:

```bash
# install from pypi
pip install jupyter_kernel_gateway

# show all config options
jupyter kernelgateway --help-all

# run it with default options
jupyter kernelgateway
```

## Contributing

The [Development page](https://jupyter-kernel-gateway.readthedocs.io/en/latest/devinstall.html) includes information about setting up a development environment and typical developer tasks.
