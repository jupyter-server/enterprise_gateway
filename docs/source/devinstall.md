## Development Installation

This document gives instructions for setup of a Dockerized development 
environment for the Jupyter Kernel Gateway.

### Prerequisites
#### Docker installation for Mac users (optional)
On a Mac, do this one-time setup if you don't have a local Docker environment
yet.

```bash
brew update

# make sure you're on Docker >= 1.7
brew install docker-machine docker
docker-machine create -d virtualbox dev
eval "$(docker-machine env dev)"
```

### Clone the repo
Clone this repository in a local directory that docker can volume mount:

```bash
# make a directory under ~ to put source
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter/kernel_gateway.git
```

### Run the tests
To run the tests:

```bash
make test-python3
make test-python2
```

### Run the gateway server
To run the gateway server:

```bash
cd kernel_gateway
make dev
```

### Access the gateway
To access the gateway instance:

1. Run `docker-machine ls` and note the IP of the dev machine.
2. Visit http://THAT_IP:8888/api in your browser where `THAT_IP` is the IP
   address returned from the previous step. (Note that the 
   route `/api/kernels` is not enabled by default for greater security. See
   the `--KernelGatewayApp.list_kernels` parameter documentation if you
   would like to enable the `/api/kernels` route.)
