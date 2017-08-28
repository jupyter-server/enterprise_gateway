## Development Workflow

This document includes instructions for setting up a development environment
for the Jupyter Elyra server. It also includes common steps in the developer
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
git clone https://github.com/jupyter/elyra.git
```

### Build a conda environment

Build a Python 3 conda environment containing the necessary dependencies for
running the elyra server, running tests, and building documentation.

```bash
make env
```

### Run the tests

Run the tests suite.

```bash
make test
```

### Run the elyra server

Run an instance of the elyra server in [`jupyter-websocket` mode](websocket-mode).

```bash
make dev
```

Then access the running server at the URL printed in the console.

Run an instance of the elyra server in [`notebook-http` mode](http-mode) using the `api_intro.ipynb` notebook in the repository.

```bash
make dev-http
```

Then access the running server at the URL printed in the console.

### Build the docs

Run Sphinx to build the HTML documentation.

```bash
make docs
```
