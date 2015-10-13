# Jupyter Kernel Gateway

A [JupyterApp](https://github.com/jupyter/jupyter_core/blob/master/jupyter_core/application.py) that implements the HTTP and Websocket resources of `/api/kernels` using [jupyter/notebook](https://github.com/jupyter/notebook), [jupyter/jupyter_client](https://github.com/jupyter/jupyter_client), and [jupyter/jupyter_core](https://github.com/jupyter/jupyter_core) as libraries. Launches kernels in its local process/filesystem space. Can be containerized and scaled out by a cluster manager (e.g., [tmpnb](https://github.com/juputer/tmpnb)). Intended to be accessed by [jupyter-js-services](https://github.com/jupyter/jupyter-js-services) and similar web-friendly clients.

## Interesting Uses

* Attach a local Jupyter Notebook server to a compute cluster in the cloud running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use kernels (e.g., dashboards)
* Scale kernels independently from clients (e.g., via [tmpnb](https://github.com/jupyter/tmpnb), [Binder](https://mybinder.org), your favorite cluster manager)

![Example diagram of how tmpnb might deploy kernel gateway + kernel containers](etc/tmpnb_kernel_gateway.png)

## What It Gives You

* Python 3 implementation of the following resources equivalent to the ones found in the latest Jupyter Notebook code base:
    * `/api` (metadata)
    * `/api/kernelspecs` (what kernels are available)
    * `/api/kernels` (kernel CRUD)
* A way to bridge the [Jupyter protocol](http://jupyter-client.readthedocs.org/en/latest/messaging.html) from Websocket to [ZeroMQ](http://zeromq.org/)
* A shared token authorization scheme
* CORS headers as options for servicing browser-based clients
* Ability to set a custom base URL (e.g., for running under tmpnb)
* A CLI for launching the kernel gateway: `jupyter kernelgateway OPTIONS`

## What It Lacks

These are in scope, but not yet implemented.

* PyPI package
* Ability to prespawn kernels
* Ability to select a default kernel
* Ability to limit # of kernels
* Ability to prepopulate kernel memory from a notebook

## Alternatives

* A Go-based implementation of a kernel gateway has also been proposed (e.g., using [rgbkrk/juno](https://github.com/rgbkrk/juno)). It will have the benefit of being a single binary that can be dropped into any environment more easily than a full Python-stack. A potential downside is that it will need to track changes in the Jupyter API and protocols whereas the Python implementation here does so implicitly.
* If your client is within the same compute cluster as the kernel and already has good ZeroMQ support, there is no need to use the kernel gateway to enable Websocket access. Talk ZeroMQ directly to the kernel.

## Try It

TODO: We're working on a PyPI package and/or Docker image. For now, if you want to install without Docker, you'll need to clone and install from the git repo.

```
git clone https://github.com/jupyter-incubator/kernel_gateway.git
cd kernel_gateway
# install from clone
pip install .
# show all config options
jupyter kernelgateway --help-all
# run it with default options
jupyter kernelgateway
```

## NodeJS Client Example

TODO: Something like the examples here [https://github.com/jupyter/jupyter-js-services#usage-examples](https://github.com/jupyter/jupyter-js-services#usage-examples)

## Python Client Example

TODO: Pull something from the test cases.

## Develop

This repository is setup for a Dockerized development environment. On a Mac, do this one-time setup if you don't have a local Docker environment yet.

```
brew update

# make sure you're on Docker >= 1.7
brew install docker-machine docker
docker-machine create -d virtualbox dev
eval "$(docker-machine env dev)"
```

Pull the Docker image that we'll use for development. We currently use the `jupyter/minimal-notebook:4.0` image because it has all the dependencies preinstalled, but it includes far more than we really need.

```
docker pull jupyter/minimal-notebook:4.0
```

Clone this repository in a local directory that docker can volume mount:

```
# make a directory under ~ to put source
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter-incubator/kernel_gateway.git
```

Run the tests:

```
make test
```

Run the gateway server:

```
cd kernel_gateway
make dev
```

To access the gateway instance:

1. Run `docker-machine ls` and note the IP of the dev machine.
2. Visit http://THAT_IP:8888/api/kernels in your browser