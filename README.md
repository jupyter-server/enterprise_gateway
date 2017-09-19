# Jupyter Elyra

[![Google Group](https://img.shields.io/badge/-Google%20Group-lightgrey.svg)](https://groups.google.com/forum/#!forum/jupyter) 
[![PyPI version](https://badge.fury.io/py/jupyter_elyra.svg)](https://badge.fury.io/py/jupyter_elyra) 
[![Build Status](https://travis-ci.org/jupyter-incubator/dashboards.svg?branch=master)](https://travis-ci.org/jupyter/elyra)
[![Code Health](https://landscape.io/github/jupyter/elyra/master/landscape.svg?style=flat)](https://landscape.io/github/jupyter/elyra/master)
[![Documentation Status](http://readthedocs.org/projects/jupyter-elyra/badge/?version=latest)](https://jupyter-kernel-gateway.readthedocs.io/en/latest/?badge=latest)

## Overview

Jupyter Elyra is is a web server that provides headless access to Jupyter kernels within an enterprise.  Built directly upon Jupyter Kernel Gateway, Jupyter Elyra leverages all of the Kernel Gateway functionality in addition to the following:
* Adds support for remote kernels hosted throughout the enterprise where kernels can be launched in the following ways:
    * Local to the Elyra server (today's Kernel Gateway behavior)
    * On specific nodes of the cluster utilizing a round-robin algorithm
    * On nodes identified by an associated resource manager
* Provides support for Yarn Resource Management out of the box.  Others can be configured via Elyra's extensible framework.
* Secure communication from the client, through the Elyra server, to the kernels
* Multi-tenant capabilities
* Ability to associate profiles consisting of configuration settings to a kernel for a given user
* Persistent kernel sessions

### Example Uses of Elyra

* ...

### Features

See the [Features page](https://jupyter-elyra.readthedocs.io/en/latest/features.html) in the 
documentation for a list of Jupyter Elyra features.

## Installation

Detailed installation instructions are located in the 
[Getting Started page](https://jupyter-elyra.readthedocs.io/en/latest/getting-started.html)
of the project docs. Here's a quick start using `pip`:

```bash
# install from pypi
pip install jupyter_elyra

# show all config options
jupyter elyra --help-all

# run it with default options
jupyter elyra
```

## Configuration

The [Configuration Options page](https://jupyter-elyra.readthedocs.io/en/latest/config-options.html) includes information about the supported options.

## Contributing

The [Development page](https://jupyter-elyra.readthedocs.io/en/latest/devinstall.html) includes information about how to contribute to Elyra, setting up a development environment and typical developer tasks.

## Roadmap

* ...


## Detailed Overview

The [Detailed Overview page](https://jupyter-elyra.readthedocs.io/en/latest/detailed-overview.html) includes information about Elyra's process proxy and launcher frameworks.

### Installation
Elyra is intended to be installed on a Kerberized HDP cluster with Spark2 and Yarn services installed and running. To support Scala kernels, Apache Toree must be installed. To support IPython kernels and R kernels to run on Yarn worker nodes, various packages have to be installed on each Yarn worker node. The commands below may have to customized to specific cluster environments.

#### Installing Elyra
Elyra is typically installed on a cluster node with a public IP address. The following commands have been verified to work on a cluster with HDP 2.6.1 installed on RHEL 7.3.

Run the following commands on the "public" node of the cluster:
```Bash
ELYRA_DOWNLOAD_SERVER="9.30.252.137"

SPARK_HOME="${SPARK_HOME:-/usr/hdp/current/spark2-client}"    # HDP

TOREE_PIP_INSTALL_PACKAGE="http://${ELYRA_DOWNLOAD_SERVER}/dist/toree/toree-0.2.0.dev1.tar.gz"

yum install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y \
    git \
    libcurl-devel.x86_64 \
    openssl-devel.x86_64 \
    python2-cryptography.x86_64 \
    python2-pip.noarch \
    R

python -m pip install --upgrade --force pip

pip install yarn-api-client

pip install --upgrade http://${ELYRA_DOWNLOAD_SERVER}/dist/elyra/elyra-0.0.2.dev0-py2.py3-none-any.whl

################################################################################

# pip-install the Apache Toree installer
pip install "${TOREE_PIP_INSTALL_PACKAGE}"

# install a new Toree Scala kernel which will be updated with Elyra's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.1" --interpreters="Scala"

# set a few helper variables
ELYRA_DEV_FOLDER="$(pip list 2> /dev/null | grep -o '/.*/elyra')"
SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"
KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

# rename the Toree Scala kernel we just installed
mv "${SCALA_KERNEL_DIR}" "${KERNELS_FOLDER}/spark_2.1_scala_yarn_cluster"

# overwrite Toree's kernel files and create remaining kernels from Elyra (including Toree Scala, IPython, R)
yes | cp -r "${ELYRA_DEV_FOLDER}/etc/kernels"/* "${KERNELS_FOLDER}/"

# replace SPARK_HOME in kernel.json files
if [[ -n "${SPARK_HOME}" && -e "${SPARK_HOME}" ]]; then
    find "${KERNELS_FOLDER}" -name "kernel.json" -type f -print -exec \
        sed -i "s|\"SPARK_HOME\": \"/usr/.*/current/spark2-client\"|\"SPARK_HOME\": \"${SPARK_HOME}\"|g" {} \;
fi

# OPTIONAL: for developers, remove --proxy-user from kernel.json files if we are not in a Kerberos secured cluster
find "${KERNELS_FOLDER}" -name kernel.json -type f -print -exec \
    sed -i 's/ --proxy-user ${KERNEL_USERNAME:-ERROR__NO__KERNEL_USERNAME}//g' {} \;
```

#### Installing Required Packages on Yarn Worker Nodes
To support IPython and R kernels, run the following commands on all Yarn worker nodes.

##### Installing Required Packaged for IPython Kernels on Yarn Worker Nodes
```Bash
yum -y install "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y python2-pip.noarch

# upgrade pip
python -m pip install --upgrade --force pip

# install IPython kernel packages
pip install ipykernel 'ipython<6.0'

# OPTIONAL: check installed packages
pip list | grep -E "ipython|ipykernel"
```

##### Installing Required Packaged for R Kernels on Yarn Worker Nodes
```Bash
yum install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y R git openssl-devel.x86_64 libcurl-devel.x86_64

# create a install script
cat <<'EOF' > install_packages.R
install.packages('git2r', repos='http://cran.rstudio.com/')
install.packages('devtools', repos='http://cran.rstudio.com/')
install.packages('RCurl', repos='http://cran.rstudio.com/')
library('devtools')
install_github('IRkernel/repr', repos='http://cran.rstudio.com/')
install_github('IRkernel/IRdisplay', repos='http://cran.rstudio.com/')
install_github('IRkernel/IRkernel', repos='http://cran.rstudio.com/')
EOF

# run the package install script in the background
R CMD BATCH install_packages.R &

# OPTIONAL: tail the progress of the installation
tail -F install_packages.Rout

# OPTIONAL: check the installed packages
ls /usr/lib64/R/library/
```

#### Starting Elyra

Create a script to start ELyra, `start_elyra.sh`, replace the variables that are flagged with `TODO: `:

```Bash
#!/bin/bash

# TODO: chose SPARK_HOME based on your cluster installation (TODO: update for your cluster)
export SPARK_HOME="${SPARK_HOME:-/usr/hdp/current/spark2-client}"

CLUSTER_NAME=$(hostname | sed -e 's/[0-9].fyre.ibm.com//')

# TODO: specify Yarn ResourceManager node, here it is on node 2 (TODO: update for your cluster)
export ELYRA_YARN_ENDPOINT=http://${CLUSTER_NAME}2.fyre.ibm.com:8088/ws/v1/cluster

# TODO: specify Yarn worker nodes, here they are node 3 and node 4 (TODO: update for your cluster)
export ELYRA_REMOTE_HOSTS=${CLUSTER_NAME}3,${CLUSTER_NAME}4

#export ELYRA_REMOTE_USER=spark
#export ELYRA_REMOTE_PWD=""
#export ELYRA_TEST_BLOCK_LAUNCH=0.0

export ELYRA_PROXY_LAUNCH_LOG=/tmp/proxy_launch.log

# launching kernels on Yarn may take longer than the default of 20 seconds
export ELYRA_KERNEL_LAUNCH_TIMEOUT=40

#export ELYRA_CONNECTION_FILE_MODE=socket

START_CMD="jupyter elyra --ip=0.0.0.0 --port=8888 --port_retries=0 --log-level=DEBUG --MappingKernelManager.cull_idle_timeout=3600 --MappingKernelManager.cull_interval=60 --JupyterWebsocketPersonality.list_kernels=True"

LOG=~/elyra.log
PIDFILE=~/elyra.pid

eval "$START_CMD > $LOG 2>&1 &"
if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```
It will start Elyra in the background.
 - to follow the log output, run `tail -F elyra.log` 
 - to stop Elyra, run `kill $(cat ~/elyra.pid)`


#### Connecting a Notebook Client to Elyra
[NB2KG](https://github.com/jupyter/kernel_gateway_demos/tree/master/nb2kg) is used to connect from a local desktop or laptop to Elyra instance on the Yarn cluster. The most convenient way to use a pre-configured installation of NB2KG would be using the Docker image [biginsights/jupyter-nb-nb2kg:dev](https://hub.docker.com/r/biginsights/jupyter-nb-nb2kg/). Replace the `<IP_OF_ELYRA_HOST>` in the command below:
```Bash
docker run -t --rm \
    -e KG_URL='http://<IP_OF_ELYRA_HOST>:8888' \
    -p 8888:8888 \
    -e KG_HTTP_USER=guest \
    -e KG_HTTP_PASS=guest-password \
    -e VALIDATE_KG_CERT='no' \
    -e LOG_LEVEL=INFO \
    -e KG_REQUEST_TIMEOUT=40 \
    -v ${HOME}/notebooks/:/tmp/notebooks \
    -w /tmp/notebooks \
    biginsights/jupyter-nb-nb2kg:dev
```

### Integration testing

Integration testing could be a manual procedure, i.e. first open a sample notebook on a web browser and then run all the codes, get all outputs and compare if the outputs are the same compared to the sample notebook ground truth outputs. However, it is also feasible to do integration testing programmatically. 

On a high level, the first step is to parse a notebook as an entity consisted of multiple code messages (inputs and outputs). Then ask a given Elyra service to create/`POST` a new kernel based on the kernel name of the notebook entity, via the JKG REST API e.g. `http://<JKG host address>/api/kernels`. After there is a kernel ID and the new kernel is ready, for each of the code cell in the notebook entity, a code message needs be sent to the Elyra service via JKG socket API connection, e.g. `ws://<JKG host address>/api/kernels/<kernel ID>/channels`. After all the outputs are received for a notebook entity, its outputs should be compared with the "ground truth" outputs on the sample notebook. If there is anything unexpected, the test could be marked as failed.
