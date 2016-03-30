# Jupyter Kernel Gateway
[![Documentation Status](http://readthedocs.org/projects/jupyter-kernel-gateway/badge/?version=latest)](http://jupyter-kernel-gateway.readthedocs.org/en/latest/?badge=latest)

## Overview

The kernel gateway is a web server that supports different mechanisms for spawning and
communicating with Jupyter kernels, such as:

* A Jupyter Notebook server-compatible HTTP API used for requesting kernels
  and talking the [Jupyter kernel protocol](https://jupyter-client.readthedocs.org/en/latest/messaging.html)
  with the kernels over Websockets
* A HTTP API defined by annotated notebook cells that maps HTTP verbs and
  resources to code to execute on a kernel

The server launches kernels in its local process/filesystem space. It can be containerized and scaled out using common technologies like [tmpnb](https://github.com/jupyter/tmpnb), [Cloud Foundry](https://github.com/cloudfoundry), and [Kubernetes](http://kubernetes.io/).

### Example Uses of Kernel Gateway

* Attach a local Jupyter Notebook server to a compute cluster in the cloud running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use kernels (e.g., web dashboards using [jupyter-js-services](https://github.com/jupyter/jupyter-js-services))
* Create microservices from notebooks using the Kernel Gateway [`notebook-http` mode](http://jupyter-kernel-gateway.readthedocs.org/en/latest/http-mode.html)

### Features

See the [Features page](https://jupyter-kernel-gateway.readthedocs.org/en/latest/features.html) in the 
documentation for a detailed explanation of Jupyter Kernel Gateway's
features.

## Installation

Detailed installation instructions can be found in the 
[Jupyter Kernel Gateway documentation](https://jupyter-kernel-gateway.readthedocs.org/en/latest/getting-started.html)
found on ReadTheDocs.

```bash
# install from pypi
pip install jupyter_kernel_gateway

# show all config options
jupyter kernelgateway --help-all

# run it with default options
jupyter kernelgateway
```

## Contributors

### Development Installation

Setting up a Dockerized development environment for the Jupyter Kernel Gateway is
straightforward using these steps:

1. Prerequisite - Docker installation (if needed)

  For example, on a Mac, do this one-time setup to set up Docker locally:

   ```bash
   brew update

   # make sure you're on Docker >= 1.7
   brew install docker-machine docker
   docker-machine create -d virtualbox dev
   eval "$(docker-machine env dev)"
   ```

2. Clone the repo.

   ```bash
   # make a directory under ~ to put source
   mkdir -p ~/projects
   cd !$

   # clone this repo
   git clone https://github.com/jupyter/kernel_gateway.git
   ```
   
3. Build the Docker dev image.

   ```bash
   make image
   ```
   
3. Run the unit tests.

   ```bash
   make test-python3
   make test-python2
   ```

4. Run the gateway server.

   ```bash
   cd kernel_gateway
   make dev
   ```

5. Access the gateway instance.

   a. Run `docker-machine ls` and note the IP of the dev machine.
   b. Visit http://THAT_IP:8888/api in your browser where `THAT_IP` is the IP
      address returned from the previous step. (Note that the 
      route `/api/kernels` is not enabled by default for greater security. See
      the `--KernelGatewayApp.list_kernels` parameter documentation if you
      would like to enable the `/api/kernels` route.)
