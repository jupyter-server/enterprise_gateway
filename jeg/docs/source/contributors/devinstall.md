# Development Workflow

Here are instructions for setting up a development environment for the [Jupyter Enterprise Gateway](https://github.com/jupyter-server/enterprise_gateway)
server. It also includes common steps in the developer workflow such as building Enterprise Gateway,
running tests, building docs, packaging kernel specifications, etc.

## Prerequisites

Install [GNU make](https://www.gnu.org/software/make/) on your system.

## Clone the repo

Clone this repository into a local directory.

```bash
# make a directory under your HOME directory to put the source code
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter-server/enterprise_gateway.git
```

## Make

Enterprise Gateway's build environment is centered around `make` and the corresponding [`Makefile`](https://github.com/jupyter-server/enterprise_gateway/blob/main/Makefile).

Entering `make` with no parameters yields the following:

```
activate                       Print instructions to activate the virtualenv (default: enterprise-gateway-dev)
clean-env                      Remove conda env
clean-images                   Remove docker images (includes kernel-based images)
clean-kernel-images            Remove kernel-based images
clean                          Make a clean source tree
dist                           Make source, binary, kernelspecs and helm chart distributions to dist folder
docker-images                  Build docker images (includes kernel-based images)
docs                           Make HTML documentation
env                            Make a dev environment
helm-chart                     Make helm chart distribution
itest-docker-debug             Run integration tests (optionally) against docker container with print statements
itest-docker                   Run integration tests (optionally) against docker swarm
itest-yarn-debug               Run integration tests (optionally) against docker demo (YARN) container with print statements
itest-yarn                     Run integration tests (optionally) against docker demo (YARN) container
kernel-images                  Build kernel-based docker images
kernelspecs                    Create archives with sample kernelspecs
lint                           Check code style
release                        Make a wheel + source release on PyPI
run-dev                        Make a server in jupyter_websocket mode
test-install                   Install and minimally run EG with the wheel and tar distributions
test                           Run unit tests
```

Some of the more useful commands are listed below.

## Build the conda environment

Build a Python 3 conda environment that can be used to run
the Enterprise Gateway server within an IDE. May be necessary prior
to [debugging Enterprise Gateway](./debug.md) based on your local Python environment.
See [Conda's Managing environments](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html#managing-environments)
for background on environments and why you may find them useful as you develop on Enterprise Gateway.

```bash
make env
```

By default, the env built will be named `enterprise-gateway-dev`. To produce a different conda env,
you can specify the name via the `ENV=` parameter.

```bash
make ENV=my-conda-env env
```

To delete your existing environment, use `clean-env` task.

```bash
make clean-env
```

## Build the wheel file

Build a wheel file that can then be installed via `pip install`

```
make bdist
```

The wheel file will reside in the `dist` directory.

## Build the kernelspec tar file

Enterprise Gateway includes several sets of kernel specifications for each of the three primary kernels: `IPython Kernel`,`IRkernel`,
and `Apache Toree` to demonstrate remote kernels and their corresponding launchers. These sets of files are then added to tar files corresponding to their target resource managers. In addition, a _combined_ tar file is also built containing all kernel specifications. Like the wheel file, these tar files will reside in the `dist` directory.

```bash
make kernelspecs
```

```{note}
Because the scala launcher requires a jar file, `make kernelspecs` requires the use of `sbt` to build the
scala launcher jar. Please consult the [sbt site](https://www.scala-sbt.org/) for directions to
install/upgrade `sbt` on your platform. We currently use version 1.3.12.
```

## Build distribution files

Builds the files necessary for a given release: the wheel file, the source tar file, and the kernel specification tar
files. This is essentially a helper target consisting of the `bdist` `sdist` and `kernelspecs` targets.

```bash
make dist
```

## Run the Enterprise Gateway server

Run an instance of the Enterprise Gateway server.

```bash
make run-dev
```

Then access the running server at the URL printed in the console.

## Build the docs

Run Sphinx to build the HTML documentation.

```bash
make docs
```

This command actually issues `make requirements html` from the `docs` sub-directory.

## Run the unit tests

Run the unit test suite.

```
make test
```

To Run a test a subset of tests, we support passing "TEST" argument to the make command as below

```
make test TEST="test_gatewayapp.py"
make test TEST="test_gatewayapp.py::TestGatewayAppConfig
make test TEST="test_gatewayapp.py::TestGatewayAppConfig::test_config_env_vars_bc"
```

## Run the integration tests

Run the integration tests suite.

These tests will bootstrap the [`elyra/enterprise-gateway-demo`](https://hub.docker.com/r/elyra/enterprise-gateway-demo/) docker image with Apache Spark using YARN resource manager and
Jupyter Enterprise Gateway and perform various tests for each kernel in local, YARN client, and YARN cluster modes.

```bash
make itest-yarn
```

## Build the docker images

The following can be used to build all docker images used within the project. See [docker images](docker.md) for specific details.

```bash
make docker-images
```

If you only want to build the kernel images, use

```bash
make kernel-images
```
