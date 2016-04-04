## Development Workflow

This document includes instructions for setting up Dockerized development environment for the Jupyter Kernel Gateway. It also includes common steps in the developer workflow such as running tests, building doc, updating specs, etc.

### Prerequisites

Install [docker](https://docs.docker.com/engine/installation) and [docker-machine](https://docs.docker.com/machine/) on your system. Create and activate a Docker VM for development.

```bash
docker-machine create -d virtualbox dev
eval "$(docker-machine env dev)"
```

### Clone the repo

Clone this repository in a local directory that your local Docker VM can volume mount:

```bash
# make a directory under ~ to put source
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter/kernel_gateway.git
```

### Build the development image

Build a Docker image containing additional dev libraries.

```bash
make image
```

### Run the tests

Run the tests suites under Python 2 and 3.

```bash
make test-python3
make test-python2
```

### Run the gateway server

Run an instance of the kernel gateway server.

```bash
make dev
```

To access the running server:

1. Run `docker-machine ls` and note the IP of the dev machine.
2. Visit http://THAT_IP:8888/api in your browser where `THAT_IP` is the IP
   address returned from the previous step.

### Build the docs

Run Sphinx to build the HTML documentation.

```bash
make docs
```

### Update the Swagger API spec

After modifying any of the APIs in `jupyter-websocket` mode, you must update the project's Swagger API specification. 

1. Load the current
[swagger.yaml](https://github.com/jupyter/kernel_gateway/blob/master/kernel_gateway/services/api/swagger.yaml) file into the [Swagger editor](http://editor.swagger.io/#/).
2. Make your changes.
3. Export both the `swagger.json` and `swagger.yaml` files.
4. Place the files in `kernel_gateway/services/api`.
5. Add, commit, and PR the changes.