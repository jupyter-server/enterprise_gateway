## Getting started

Jupyter Enterprise Gateway requires Python (Python 3.3 or greater, or Python 2.7) and is intended
to be installed on a [Apache Spark 2.x](http://spark.apache.org/docs/latest/index.html) cluster.

The following Resource Managers are supported with the Jupyter Enterprise Gateway:

* Spark Standalone
* YARN Resource Manager - Client Mode
* YARN Resource Manager - Cluster Mode

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

To support Scala kernels, [Apache Toree](https://toree.apache.org/) must be installed. To support
IPython kernels and R kernels to run in YARN containers, various packages have to be installed
on each of the YARN data nodes. The simplest way to enable all the data nodes with required
dependencies is to install [Anaconda](https://anaconda.com/) on all cluster nodes.

To take full advantage of security and user impersonation capabilities, a Kerberized cluster
is recommended.

### Enterprise Gateway Features

Jupyter Enterprise Gateway exposes the following features and functionality:

* Enables the ability to launch kernels on different servers thereby distributing resource utilization 
across the enterprise
* Pluggable framework allows for support of additional resource managers
* Secure communication from client to kernel
* Persistent kernel sessions (see [Roadmap](roadmap.html#project-roadmap))
* Configuration profiles (see [Roadmap](roadmap.html#project-roadmap))
* Feature parity with [Jupyter Kernel Gateway](http://jupyter-kernel-gateway.readthedocs.io/en/latest/)
* A CLI for launching the enterprise gateway server: `jupyter enterprisegateway OPTIONS`
* A Python 2.7 and 3.3+ compatible implementation


### Installing Enterprise Gateway

For new users, we **highly recommend** [installing Anaconda](http://www.anaconda.com/download).
Anaconda conveniently installs Python, the [Jupyter Notebook](http://jupyter.readthedocs.io/en/latest/install.html), the [IPython kernel](http://ipython.readthedocs.io/en/stable/install/kernel_install.html) and other commonly used
packages for scientific computing and data science.

Use the following installation steps:

* Download [Anaconda](http://www.anaconda.com/download). We recommend downloading Anaconda’s
latest Python version (currently Python 2.7 and Python 3.6).

* Install the version of Anaconda which you downloaded, following the instructions on the download
page.

* Install the latest version of Jupyter Enterprise Gateway from [PyPI](https://pypi.python.org/pypi/jupyter_enterprise_gateway/0.6.0)
using `pip`(part of Anaconda) along with its dependencies.

```bash
# install using pip from pypi
pip install --upgrade jupyter_enterprise_gateway
```

```bash
# install using conda from conda forge
conda install -c conda-forge jupyter_enterprise_gateway
```

At this point, the Jupyter Enterprise Gateway deployment provides local kernel support which is
fully compatible with Jupyter Kernel Gateway.

To uninstall Jupyter Enterprise Gateway...
```bash
#uninstall using pip
pip uninstall jupyter_enterprise_gateway
```

```bash
#uninstall using conda
conda uninstall jupyter_enterprise_gateway
```

### Installing Kernels

Please follow the link below to learn more specific details about how to install/configure specific
kernels with Jupyter Enterprise Gateway:

* [Installing and Configuring kernels](getting-started-kernels.md)

### Configuring Spark Resource Managers

To leverage the full distributed capabilities of Spark, Jupyter Enterprise Gateway has provided
deep integrarion with YARN resource manager. Having said that, EG also supports running in 
pseudo-distributed utilizing both YARN client or Spark Standalone modes. 

Please follow the links below to learn more specific details about how to enable/configure
the different modes: 

* [Enabling Cluster Mode support](getting-started-cluster-mode.md)
* [Enabling Client Mode/Standalone support](getting-started-client-mode.md)

### Starting Enterprise Gateway
Very few arguments are necessary to minimally start Enterprise Gateway.  The following command 
could be considered a minimal command:

```bash
jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0
```

where `--ip=0.0.0.0` exposes Enterprise Gateway on the public network and `--port_retries=0` ensures
that a single instance will be started.

We recommend starting Enterprise Gateway as a background task.  As a result, you might find it best 
to create a start script to maintain options, file redirection, etc.

The following script starts Enterprise Gateway with `DEBUG` tracing enabled (default is `INFO`) and idle
kernel culling for any kernels idle for 12 hours where idle check intervals occur every minute.  
The Enterprise Gateway log can then be monitored via `tail -F enterprise_gateway.log` and it can be 
stopped via `kill $(cat enterprise_gateway.pid)`

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG > $LOG 2>&1 &
if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

### Connecting a Notebook to Enterprise Gateway

[NB2KG](https://github.com/jupyter/kernel_gateway_demos/tree/master/nb2kg) is used to connect from a
local desktop or laptop to the Enterprise Gateway instance on the Spark/YARN cluster. We strongly recommend
that the latest version of NB2KG be used as our team has provided some security enhancements to enable for [conveying the notebook 
user](https://github.com/jupyter/kernel_gateway_demos/pull/48) (for configurations when Enterprise Gateway is
running behind a secured gateway) and allowing for [increased request 
timeouts](https://github.com/jupyter/kernel_gateway_demos/pull/55) (due to the longer kernel startup times 
when interacting with the resource manager or distribution operations). Please follow the [developer 
instructions](https://github.com/jupyter/kernel_gateway_demos/tree/master/nb2kg#develop) to build the
latest version until a new release is available (at which time we'll update this information and likely
include instructions for building a docker image).

Extending the notebook launch command listed on the [NB2KG 
repo](https://github.com/jupyter/kernel_gateway_demos/tree/master/nb2kg#run-notebook-server), 
one might use the following...

```bash
export KG_URL=http://<ENTERPRISE_GATEWAY_HOST_IP>:8888
export KG_HTTP_USER=guest
export KG_HTTP_PASS=guest-password
export KG_REQUEST_TIMEOUT=30
export KERNEL_USERNAME=${KG_HTTP_USER}
jupyter notebook \
  --NotebookApp.session_manager_class=nb2kg.managers.SessionManager \
  --NotebookApp.kernel_manager_class=nb2kg.managers.RemoteKernelManager \
  --NotebookApp.kernel_spec_manager_class=nb2kg.managers.RemoteKernelSpecManager
```

For your convenience, we have also build a docker image with latest Jupyter Notebook and latest NB2KG which can be launched
by the command below:

```bash
docker run -t --rm \
  -e KG_URL='http://<master ip>:8888' \
  -e KG_HTTP_USER=guest \ 
  -e KG_HTTP_PASS=guest-password \ 
  -p 8888:8888 \
  -e VALIDATE_KG_CERT='no' \
  -e LOG_LEVEL=DEBUG \
  -e KG_REQUEST_TIMEOUT=40 \
  -e KG_CONNECT_TIMEOUT=40 \
  -v ${HOME}/notebooks/:/tmp/notebooks \
  -w /tmp/notebooks \
  elyra/nb2kg
```
