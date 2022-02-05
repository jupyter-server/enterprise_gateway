# Getting started

Jupyter Enterprise Gateway requires Python (Python 3.6 or greater) and is intended to be installed on a node (typically the primary node) of a managed cluster.  Although its design center is for running kernels in [Apache Spark](https://spark.apache.org/docs/latest/index.html) clusters, clusters configured without Apache Spark are also supported.

The following Resource Managers are currently supported with Jupyter Enterprise Gateway:

* Kubernetes
* Docker Swarm
* Hadoop YARN
* Spark Standalone
* IBM Spectrum Conductor

If you don't rely on a Resource Manager, you can use the Distributed mode which will distribute kernels across a set of hosts via SSH.

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with [Apache Toree](https://toree.apache.org/) kernel
* R/Apache Spark 2.x with IRkernel

To take full advantage of security and user impersonation capabilities, a Kerberized cluster is recommended.

## Installing Enterprise Gateway

For new users, we **highly recommend** [installing Anaconda](https://www.anaconda.com/download).
Anaconda conveniently installs Python, the [Jupyter Notebook](https://jupyter.readthedocs.io/en/latest/install.html), the [IPython kernel](http://ipython.readthedocs.io/en/stable/install/kernel_install.html) and other commonly used
packages for scientific computing and data science.

Use the following installation steps:

* Download [Anaconda](https://www.anaconda.com/download). We recommend downloading Anaconda’s
latest Python version (currently Python 3.9).

* Install the version of Anaconda which you downloaded, following the instructions on the download page.

* Install the latest version of Jupyter Enterprise Gateway from [PyPI](https://pypi.python.org/pypi/jupyter_enterprise_gateway/)
or [conda forge](https://conda-forge.org/) along with its dependencies.

```bash
# install using pip from pypi
pip install --upgrade jupyter_enterprise_gateway
```

```bash
# install using conda from conda forge
conda install -c conda-forge jupyter_enterprise_gateway
```

At this point, the Jupyter Enterprise Gateway deployment provides local kernel support which is fully compatible with Jupyter Kernel Gateway.  

To uninstall Jupyter Enterprise Gateway...
```bash
#uninstall using pip
pip uninstall jupyter_enterprise_gateway
```

```bash
#uninstall using conda
conda uninstall jupyter_enterprise_gateway
```

## Installing Kernels

To leverage the full distributed capabilities of Spark, Jupyter Enterprise Gateway has provided deep integration with various resource managers. Having said that, Enterprise Gateway also supports running in a pseudo-distributed mode utilizing for example both YARN client or Spark Standalone modes. We've also recently added Kubernetes, Docker Swarm and IBM Spectrum Conductor integrations.

Please follow the links below to learn specific details about how to enable/configure the different modes of deploying your kernels:

* [Distributed](kernel-distributed.md)
* [YARN Cluster Mode](kernel-yarn-cluster-mode.md)
* [YARN Client Mode](kernel-yarn-client-mode.md)
* [Spark Standalone](kernel-spark-standalone.md)
* [Kubernetes](kernel-kubernetes.md)
* [Docker Swarm](kernel-docker.md)
* [IBM Spectrum Conductor](kernel-conductor.md)
* [Standalone Remote Kernel Execution](kernel-library.md)

In each of the resource manager sections, we set the `KERNELS_FOLDER` to `/usr/local/share/jupyter/kernels` since that's one of the default locations searched by the Jupyter framework.  Co-locating kernelspecs hierarchies in the same parent folder is recommended, although not required.

Depending on the resource manager, we detail in the related section the implemented kernel languages (python, scala, R...). The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

### Important Requirements regarding the Nodes

We have three cases:

*Case 1 - The kernel is run in via a container-based process proxy (Kubernetes, Docker or DockerSwarm)*

In that case, the image should ensure the availability of the kernel libraries and kernelspec. The kernelspec is not necessary here, only the launcher. We talk about this in [container customization](./docker.html#bringing-your-own-kernel-image).

The launch of containerized kernels via Enterprise Gateway is two-fold.

1. First, there's the argv section in the kernelspec that is processed by the server. In these cases, the command that is invoked is a python script using the target container's api (kubernetes, docker, or docker swarm) that is responsible for converting any necessary "parameters" to environment variables, etc. that are used during the actual container creation.
2. The command that is run in the container is actually the kernel launcher script. This script is responsible for taking the response address (which is now an env variable) and returning the kernel's connection information back on that response address to Enterprise Gateway. The kernel launcher does additional things - but primarily listens for interrupt and shutdown requests, which it then passes along to the actual (embedded) kernel.

So container environments have two launches - one to launch the container itself, the other to launch the kernel (within the container).

*Case 2 - The kernel is run via DistributedProcessProxy*

The kernelspecs are required on all nodes if using the DistributedProcessProxy - which apply to YARN Client mode, Standalone, and Distributed modes. All kernels (libraries...) and their corresponding kernelspecs must reside on each node. 

The kernelspec hierarchies (i.e., paths) must be available and identical on all nodes. 

IPython and IRkernel kernels must be installed on each node.

SSH passwordless is needed between the EG node and the other nodes.

*Case 3 - The kernel is run via YarnClusterProcessProxy or ConductorClusterProcessProxy*

With cluster process proxies, distribution of kernelspecs to all nodes besides the EG node is not required.

However, the IPython and IRkernel kernels must be installed on each node.

Note that because the Apache Toree kernel, and its supporting libraries, will be transferred to the target node via spark-submit, installation of Apache Toree (the scala kernel) is not required except on the Enterprise Gateway node itself.

### Sample kernelspecs

We provide sample kernel configuration and launcher tar files as part of [each release](https://github.com/jupyter/enterprise_gateway/releases) (e.g. [jupyter_enterprise_gateway_kernelspecs-2.5.0.tar.gz](https://github.com/jupyter/enterprise_gateway/releases/download/v2.5.0/jupyter_enterprise_gateway_kernelspecs-2.5.0.tar.gz)) that can be extracted and modified to fit your configuration.

For information about how to build your own kernel-based docker image for use by Enterprise Gateway see [Custom kernel images](docker.html#custom-kernel-images).

## Starting Enterprise Gateway

Very few arguments are necessary to minimally start Enterprise Gateway.  The following command could be considered a minimal command:

```bash
jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0
```

where `--ip=0.0.0.0` exposes Enterprise Gateway on the public network and `--port_retries=0` ensures that a single instance will be started.

_Please note that the ability to target resource-managed clusters (and use remote kernels) will require additional configuration settings depending on the resource manager.  For additional information see the appropriate "Enabling ... Support" section listed above._

We recommend starting Enterprise Gateway as a background task.  As a result, you might find it best to create a start script to maintain options, file redirection, etc.

The following script starts Enterprise Gateway with `DEBUG` tracing enabled (default is `INFO`) and idle kernel culling for any kernels idle for 12 hours where idle check intervals occur every minute.  The Enterprise Gateway log can then be monitored via `tail -F enterprise_gateway.log` and it can be stopped via `kill $(cat enterprise_gateway.pid)`

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

## Enterprise Gateway Features (TODO)

Jupyter Enterprise Gateway exposes the following features and functionality:

* Enables the ability to launch kernels on different servers thereby distributing resource utilization across the enterprise
* Pluggable framework allows for support of additional resource managers
* Secure communication from client to kernel
* Persistent kernel sessions (see [Roadmap](roadmap.html#project-roadmap))
* Configuration profiles (see [Roadmap](roadmap.html#project-roadmap))
* Feature parity with [Jupyter Kernel Gateway's](https://jupyter-kernel-gateway.readthedocs.io/en/latest/) websocket-mode.
* A CLI for launching the enterprise gateway server: `jupyter enterprisegateway OPTIONS`
* A Python 3.6+ compatible implementation

Note that Enterprise Gateway also supports local kernels by default.  However, HA/DR functionality won't be affective unless kernels run remotely.
