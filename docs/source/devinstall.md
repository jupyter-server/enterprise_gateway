## Development Workflow

This document includes instructions for setting up a development environment
for the Jupyter Kernel Gateway. It also includes common steps in the developer
workflow such as running tests, building docs, updating specs, etc.

### Prerequisites

Install [miniconda](https://conda.io/miniconda.html) and GNU make on your system.

### Clone the repo

Clone this repository in a local directory.

```bash
# make a directory under ~ to put source
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter/kernel_gateway.git
```

### Build a conda environment

Build a Python 3 conda environment containing the necessary dependencies for
running the kernel gateway, running tests, and building documentation.

```bash
make env
```

### Run the tests

Run the tests suite.

```bash
make test
```

### Run the gateway server

Run an instance of the kernel gateway server in [`jupyter-websocket` mode](websocket-mode).

```bash
make dev
```

Then access the running server at the URL printed in the console.

Run an instance of the kernel gateway server in [`notebook-http` mode](http-mode) using the `api_intro.ipynb` notebook in the repository.

```bash
make dev-http
```

Then access the running server at the URL printed in the console.

### Build the docs

Run Sphinx to build the HTML documentation.

```bash
make docs
```

### Update the Swagger API spec

After modifying any of the APIs in `jupyter-websocket` mode, you must update the project's Swagger API specification.

1. Load the current
[swagger.yaml](https://github.com/jupyter/kernel_gateway/blob/master/kernel_gateway/jupyter_websocket/swagger.yaml) file into the [Swagger editor](http://editor.swagger.io/#/).
2. Make your changes.
3. Export both the `swagger.json` and `swagger.yaml` files.
4. Place the files in `kernel_gateway/jupyter_websocket`.
5. Add, commit, and PR the changes.
