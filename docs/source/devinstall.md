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

```python
activate                       eval `make activate`
bdist                          Make a dist/*.whl binary distribution
clean                          Make a clean source tree
dev                            Make a server in jupyter_websocket mode
docs                           Make HTML documentation
env                            Make a dev environment
install                        Make a conda env with dist/*.whl and dist/*.tar.gz installed
kernelspecs                    Make a tar.gz file consisting of kernelspec files
nuke                           Make clean + remove conda env
release                        Make a wheel + source release on PyPI
sdist                          Make a dist/*.tar.gz source distribution
test                           Make a python3 test run

```
Some of the more useful commands are listed below.

### Build a conda environment

Build a Python 3 conda environment containing the necessary dependencies for
running the enterprise gateway server, running tests, and building documentation.

```bash
make env
```

By default, the env built will be named `enterprise-gateway-dev`.  To produce a different conda env, 
you can specify the name via the `ENV=` parameter. 

```bash
make ENV=my-conda-env env
```

>**Note:** If using a non-default conda env, all `make` commands should include the `ENV=` parameter, 
otherwise the command will use the default environment.

### Build the wheel file

Build a wheel file that can then be installed via `pip install`

```bash
make bdist
```

### Build the kernelspec tar file

Enterprise Gateway includes two sets of kernelspecs for each of the three primary kernels: `IPython`,`IR`, 
and `Toree` to demonstrate remote kernels and their corresponding launchers.  One set uses the 
`DistributedProcessProxy` while the other uses  the `YarnClusterProcessProxy`. The following makefile 
target produces a tar file (`enterprise_gateway_kernelspecs.tar.gz`) in the `dist` directory.

```bash
make kernelspecs
```

### Run the Enterprise Gateway server

Run an instance of the Enterprise Gateway server.

```bash
make dev
```

Then access the running server at the URL printed in the console.

### Build the docs

Run Sphinx to build the HTML documentation.

```bash
make docs
```

### Run the unit tests

Run the unit test suite.

```bash
make test
```

### Integration testing

Integration testing could be a manual procedure, i.e. first open a sample notebook on a web browser 
and then run all the codes, get all outputs and compare if the outputs are the same compared to the 
sample notebook *ground truth* outputs. However, it is also feasible to do integration testing 
programmatically. 

On a high level, the first step is to parse a notebook as an entity consisted of multiple code messages 
(inputs and outputs). Then ask a given Enterprise Gateway service to create (via `POST`) a new kernel 
based on the kernel name of the notebook entity, via the REST API e.g. 
`http://<Enterprise Gateway Host IP and Port>/api/kernels`. After there is a kernel ID and the new 
kernel is ready, for each of the code cell in the notebook entity, a code message needs be sent to 
the Enterprise Gateway service via socket API connection, e.g. 
`ws://<Enterprise Gateway Host IP and Port>/api/kernels/<kernel ID>/channels`. After all the outputs 
are received for a notebook entity, its outputs should be compared with the *ground truth* outputs 
on the sample notebook. If there is anything unexpected, the test could be marked as failed.
