**[Technical Overview](#technical-overview)** |
**[Features](#features)** |
**[Installation](#installation)** |
**[System Architecture](#system-architecture)** |
**[Contributing](#contributing)** |

# Jupyter Enterprise Gateway

[![PyPI version](https://badge.fury.io/py/jupyter_enterprise_gateway.svg)](https://badge.fury.io/py/jupyter_enterprise_gateway) 
[![Build Status](https://travis-ci.org/jupyter/enterprise_gateway.svg?branch=master)](https://travis-ci.org/jupyter/enterprise_gateway)
[![Documentation Status](http://readthedocs.org/projects/jupyter-enterprise-gateway/badge/?version=latest)](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/?badge=latest)
[![Coverage Status](https://codecov.io/github/jupyter/enterprise_gateway/coverage.svg?branch=master)](https://codecov.io/github/jupyter/enterprise_gateway?branch=master)
[![Google Group](https://img.shields.io/badge/google-group-blue.svg)](https://groups.google.com/forum/#!forum/jupyter)

Jupyter Enterprise Gateway enables Jupyter Notebook to launch remote kernels in a distributed cluster,
including Apache Spark managed by YARN, IBM Spectrum Conductor, Kubernetes or Docker Swarm.

It provides out of the box support for the following kernels:

* Python using IPython kernel
* R using IRkernel
* Scala using Apache Toree kernel

Full Documentation for Jupyter Enterprise Gateway can be found [here](http://jupyter-enterprise-gateway.readthedocs.io/en/latest)

Jupyter Enterprise Gateway does not manage multiple Jupyter Notebook deployments, for that
you should look for [JupyterHub](https://github.com/jupyterhub/jupyterhub).

## Technical Overview

Jupyter Enterprise Gateway is a web server that provides headless access to Jupyter kernels within 
an enterprise.  Built directly upon Jupyter Kernel Gateway, Jupyter Enterprise Gateway leverages all 
of the Kernel Gateway functionality in addition to the following:
* Adds support for remote kernels hosted throughout the enterprise where kernels can be launched in 
the following ways:
    * Local to the Enterprise Gateway server (today's Kernel Gateway behavior)
    * On specific nodes of the cluster utilizing a round-robin algorithm
    * On nodes identified by an associated resource manager
* Provides support Apache Spark managed by YARN, IBM Spectrum Conductor, Kubernetes or Docker Swarm out of the box.  
Others can be configured via Enterprise Gateway's extensible framework.
* Secure communication from the client, through the Enterprise Gateway server, to the kernels
* Multi-tenant capabilities
* Ability to associate profiles consisting of configuration settings to a kernel for a given user
* Persistent kernel sessions

![Deployment Diagram](https://github.com/jupyter/enterprise_gateway/blob/master/docs/source/images/deployment.png?raw=true)

## Features

See [Enterprise Gateway Features](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/getting-started.html#enterprise-gateway-features) in the 
documentation for a list of Jupyter Enterprise Gateway features.

## Installation

Detailed installation instructions are located in the 
[Getting Started page](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/getting-started.html)
of the project docs. Here's a quick start using `pip`:

```bash
# install from pypi
pip install --upgrade jupyter_enterprise_gateway

# show all config options
jupyter enterprisegateway --help-all

# run it with default options
jupyter enterprisegateway
```

Please check the [Configuration Options page](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/config-options.html) 
for information about the supported options.

## System Architecture

The [System Architecture page](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/system-architecture.html) 
includes information about Enterprise Gateway's remote kernel, process proxy, and launcher frameworks.

## Contributing

The [Contribution page](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/contrib.html) includes 
information about how to contribute to Enterprise Gateway along with our roadmap.  While there, you'll want to
[set up a development environment](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/devinstall.html) and check out typical developer tasks.

