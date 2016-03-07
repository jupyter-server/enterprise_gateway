# Jupyter Kernel Gateway

A web server that supports different mechanisms for spawning and
communicating with Jupyter kernels, such as:

* A Jupyter Notebook server-compatible HTTP API used for requesting kernels
  and talking the [Jupyter kernel protocol](http://jupyter-client.readthedocs.org/en/latest/messaging.html)
  with the kernels over Websockets
* A HTTP API defined by annotated notebook cells that maps HTTP verbs and
  resources to code to execute on a kernel

The server launches kernels in the server's local process/filesystem space.
The server can be containerized and scaled out by a cluster manager (e.g.,
[tmpnb](https://github.com/jupyter/tmpnb)).

## Installation

Detailed installation instructions can be found in the 
[Jupyter Kernel Gateway documentation](http://jupyter-kernel-gateway.readthedocs.org/en/latest/)
found on ReadTheDocs.

### Using pip

```bash
# install from pypi
pip install jupyter_kernel_gateway

# show all config options
jupyter kernelgateway --help-all

# run it with default options
jupyter kernelgateway
```
### Using Docker

Getting started with Jupyter Kernel Gateway and Docker is an option too.
Just follow the steps below for [Development Installation](#Development%20Installation).

## Contributors

### Development Installation

Setting up a Dockerized development environment for the Jupyter Kernel Gateway is
straightforward using these steps:

1. Prerequisite - Docker installation (if needed)

   On a Mac, do this one-time setup to set up Docker locally:

   ```bash
   brew update

   # make sure you're on Docker >= 1.7
   brew install docker-machine docker
   docker-machine create -d virtualbox dev
   eval "$(docker-machine env dev)"
   ```

2. Clone the repo

   ```bash
   # make a directory under ~ to put source
   mkdir -p ~/projects
   cd !$

   # clone this repo
   git clone https://github.com/jupyter/kernel_gateway.git
   ```
   
3. Test the installation

   ```bash
   make test-python3
   make test-python2
   ```

4. Run the gateway server

   ```bash
   cd kernel_gateway
   make dev
   ```

5. Access the gateway instances:

   a. Run `docker-machine ls` and note the IP of the dev machine.
   
   b. Visit http://THAT_IP:8888/api in your browser where `THAT_IP` is the IP
      address returned from the previous step. (Note that the 
      route `/api/kernels` is not enabled by default for greater security. See
      the `--KernelGatewayApp.list_kernels` parameter documentation if you
      would like to enable the `/api/kernels` route.)
