## Development Workflow

Here are instructions for setting up a development environment for the Jupyter Enterprise Gateway 
server. It also includes common steps in the developer workflow such as building Enterprise Gateway, 
running tests, building docs, packaging kernelspecs, etc.

### Prerequisites

Install [miniconda](https://conda.io/miniconda.html) and [GNU make](https://www.gnu.org/software/make/) on your system.

### Clone the repo

Clone this repository in a local directory.

```bash
# make a directory under ~ to put source
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter/enterprise_gateway.git
```
### Make

Enterprise Gateway's build environment is centered around `make` and the corresponding `Makefile`.  
Entering `make` with no parameters yields the following:

```
activate                       eval `make activate`
bdist                          Make a dist/*.whl binary distribution
clean                          Make a clean source tree
dev                            Make a server in jupyter_websocket mode
docker_clean                   Remove docker images
docker_clean_enterprise-gateway Remove elyra/enterprise-gateway:dev docker image
docker_clean_hadoop-spark      Remove elyra/hadoop-spark:2.7.0-2.1.0 docker image
docker_clean_nb2kg             Remove elyra/nb2kg:dev docker image
docker_image_enterprise-gateway Build elyra/enterprise-gateway:dev docker image
docker_image_hadoop-spark      Build elyra/hadoop-spark:2.7.1-2.1.0 docker image
docker_image_nb2kg             Build elyra/nb2kg:dev docker image 
docker_images                  Build docker images
docs                           Make HTML documentation
env                            Make a dev environment
install                        Make a conda env with dist/*.whl and dist/*.tar.gz installed
itest                          Run integration tests against docker container
kernelspecs                    Make a tar.gz file consisting of kernelspec files
nuke                           Make clean + remove conda env
release                        Make a wheel + source release on PyPI
sdist                          Make a dist/*.tar.gz source distribution
test                           Run unit tests
```
Some of the more useful commands are listed below.

### Build a conda environment

Build a Python 3 conda environment containing the necessary dependencies for
running the enterprise gateway server, running tests, and building documentation.

```
make env
```

By default, the env built will be named `enterprise-gateway-dev`.  To produce a different conda env, 
you can specify the name via the `ENV=` parameter. 

```
make ENV=my-conda-env env
```

>**Note:** If using a non-default conda env, all `make` commands should include the `ENV=` parameter, 
otherwise the command will use the default environment.

### Build the wheel file

Build a wheel file that can then be installed via `pip install`

```
make bdist
```

### Build the kernelspec tar file

Enterprise Gateway includes two sets of kernelspecs for each of the three primary kernels: `IPython`,`IR`, 
and `Toree` to demonstrate remote kernels and their corresponding launchers.  One set uses the 
`DistributedProcessProxy` while the other uses  the `YarnClusterProcessProxy`. The following makefile 
target produces a tar file (`enterprise_gateway_kernelspecs.tar.gz`) in the `dist` directory.

```
make kernelspecs
```

### Run the Enterprise Gateway server

Run an instance of the Enterprise Gateway server.

```
make dev
```

Then access the running server at the URL printed in the console.

### Build the docs

Run Sphinx to build the HTML documentation.

```
make docs
```

### Run the unit tests

Run the unit test suite.

```
make test
```

### Build the docker images

The following can be used to build all three docker images used within the project.  See 
[docker images](docker.html) for specific details.

```
make docker_images
```