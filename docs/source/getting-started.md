## Getting started

Jupyter Enterprise Gateway requires Python (Python 3.3 or greater, or Python 2.7) and is intended to be installed on a node (typically the master node) of a managed cluster.  Although its design center is for running kernels in [Apache Spark 2.x](http://spark.apache.org/docs/latest/index.html) clusters, clusters configured without Apache Spark are also acceptable.

The following Resource Managers are supported with the Jupyter Enterprise Gateway:

* Spark Standalone
* YARN Resource Manager - Client Mode
* YARN Resource Manager - Cluster Mode
* IBM Spectrum Conductor - Cluster Mode
* Kubernetes
* Docker Swarm

If you don't rely on a Resource Manager, you can use the Distributed mode which will connect a set of hosts via SSH.

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

To support Scala kernels, [Apache Toree](https://toree.apache.org/) is used. To support IPython kernels and R kernels, various packages have to be installed on each of the resource manager nodes. The simplest way to enable all the data nodes with required dependencies is to install [Anaconda](https://anaconda.com/) on all cluster nodes.

To take full advantage of security and user impersonation capabilities, a Kerberized cluster is recommended.

### Enterprise Gateway Features

Jupyter Enterprise Gateway exposes the following features and functionality:

* Enables the ability to launch kernels on different servers thereby distributing resource utilization across the enterprise
* Pluggable framework allows for support of additional resource managers
* Secure communication from client to kernel
* Persistent kernel sessions (see [Roadmap](roadmap.html#project-roadmap))
* Configuration profiles (see [Roadmap](roadmap.html#project-roadmap))
* Feature parity with [Jupyter Kernel Gateway's](http://jupyter-kernel-gateway.readthedocs.io/en/latest/) websocket-mode.
* A CLI for launching the enterprise gateway server: `jupyter enterprisegateway OPTIONS`
* A Python 2.7 and 3.3+ compatible implementation


### Kernel Gateway vs. Enterprise Gateway
Enterprise Gateway was formerly built directly on Kernel Gateway.  At that time, it had complete feature parity with Kernel Gateway.  However, in order to address various roadmap items, Enterprise Gateway removed its dependency on Kernel Gateway, so now the question arises, when does one choose Enterprise Gateway over Kernel Gateway?

#### Use Enterprise Gateway if...
1. You have a large computer cluster consisting of limited resources (GPUs, large memory, etc) and users require those resources from notebooks
2. You have large numbers of users requiring access to a shared compute cluster
3. You require some amount of High Availability/Disaster Recovery such that another Gateway server can be spun up to service existing (and remote) kernels

#### Use Kernel Gateway if...
1. You have a small user pool where the resources of the Gateway server can be shared amongst those users (no remote kernel support)
2. You wish to configured the [notebook-http mode](https://jupyter-kernel-gateway.readthedocs.io/en/latest/http-mode.html) functionality where a specific Notebook provides HTTP endpoints

Note that Enterprise Gateway also supports local kernels by default.  However, HA/DR functionality won't be affective unless kernels run remotely.

### Installing Enterprise Gateway

For new users, we **highly recommend** [installing Anaconda](http://www.anaconda.com/download).
Anaconda conveniently installs Python, the [Jupyter Notebook](http://jupyter.readthedocs.io/en/latest/install.html), the [IPython kernel](http://ipython.readthedocs.io/en/stable/install/kernel_install.html) and other commonly used
packages for scientific computing and data science.

Use the following installation steps:

* Download [Anaconda](http://www.anaconda.com/download). We recommend downloading Anaconda’s
latest Python version (currently Python 2.7 and Python 3.6).

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

### Installing Kernels

To leverage the full distributed capabilities of Spark, Jupyter Enterprise Gateway has provided deep integration with various resource managers. Having said that, Enterprise Gateway also supports running in a pseudo-distributed mode utilizing for example both YARN client or Spark Standalone modes. We've also recently added Kubernetes, Docker Swarm and IBM Spectrum Conductor integrations.

Please follow the links below to learn specific details about how to enable/configure the different modes of depoloying your kernels:

* [Distributed](kernel-distributed.html)
* [YARN Cluster Mode](kernel-yarn-cluster-mode.html)
* [YARN Client Mode](kernel-yarn-client-mode.html)
* [Standalone](kernel-spark-standalone.html)
* [Kubernetes](kernel-kubernetes.html)
* [Docker Swarm](kernel-docker.html)
* [IBM Spectrum Conducto](kernel-conductor.html)

In each of the resource manager sections, we set the `KERNELS_FOLDER` to `/usr/local/share/jupyter/kernels` since that's one of the default locations searched by the Jupyter framework.  Co-locating kernelspecs hierarchies in the same parent folder is recommended, although not required.

Depending on the resource manager, we detail in the related section the implemented kernel languages (python, scala, R...). The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

#### Important Requirements regarding the Nodes

We have three cases:

*Case 1 - The kernel is run in via a container-based process proxy (Kubernetes, Docker or DockerSwarm)*

In that case, the image should ensure the availability of the kernel libraries and kernelspec. The kernelspec is not necessary here, only the launcher. We talk about this in [container customization](./docker.html#bringing-your-own-kernel-image).

The launch of containerized kernels via Enterprise Gateway is two-fold.

1. First, there's the argv section in the kernelspec that is processed by the server. In these cases, the command that is invoked is a python script using the target container's api (kubernetes, docker, or docker swarm) that is responsible for converting any necessary "parameters" to environment variables, etc. that are used during the actual container creation.
2. The command that is run in the container is the actual kernel launcher script. This launcher is responsible for taking the response address (which is now an env variable) and returning the kernel's connection information back on that response address to Enterprise Gateway. The kernel launcher does additional things - but primarily listens for interrupt and shutdown requests, which it then passes along to the actual (embedded) kernel.

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

#### Sample kernelspecs

We provide sample kernel configuration and launcher tar files as part of [each release](https://github.com/jupyter/enterprise_gateway/releases) (e.g. [jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz](https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz)) that can be extracted and modified to fit your configuration.

For information about how to build your own kernel-based docker image for use by Enterprise Gateway see [Custom kernel images](docker.html#custom-kernel-images).

### Starting Enterprise Gateway

Very few arguments are necessary to minimally start Enterprise Gateway.  The following command could be considered a minimal command and essentially provides functionality equal to Jupyter Kernel Gateway:

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

### Connecting a Notebook to Enterprise Gateway

To leverage the benefits of Enterprise Gateway, it's helpful to redirect a Notebook server's kernel management to the Gateway server.  This allows better separation of the user's notebooks from the managed computer cluster (Kubernetes, Hadoop YARN, Docker Swarm, etc.) on which Enterprise Gateway resides.  A Notebook server can be configured to relay kernel requests to an Enterprise Gateway server in two ways - depending on the version of Notebook you're using.

#### Notebook 6.0 (and above)
With the Notebook 6.0 release, the NB2KG server extension (see next section) is built directly into the Notebook server.  As a result, the steps for installing and configuring the server extension are no longer necessary.

To start the notebook server from the command line, the following will redirect kernel management request to the Gateway server running at `<ENTERPRISE_GATEWAY_HOST_IP>`:
```bash
jupyter notebook --gateway-url=http://<ENTERPRISE_GATEWAY_HOST_IP>:8888 --GatewayClient.http_user=guest --GatewayClient.http_pwd=guest-password
```

If you have Notebook already in a docker image, a corresponding docker invocation would look something like this:
```bash
docker run -t --rm \
  -e JUPYTER_GATEWAY_URL='http://<master ip>:8888' \
  -e JUPYTER_GATEWAY_HTTP_USER=guest \
  -e JUPYTER_GATEWAY_HTTP_PWD=guest-password \
  -e JUPYTER_GATEWAY_VALIDATE_CERT='false' \
  -e LOG_LEVEL=DEBUG \
  -p 8888:8888 \
  -v ${HOME}/notebooks/:/tmp/notebooks \
  -w /tmp/notebooks \
  notebook-docker-image
```

Notebook files residing in `${HOME}/notebooks` can then be accessed via `http://localhost:8888`.  

#### NB2KG Server Extension
For Notebook versions prior to 6.0, the [NB2KG](https://github.com/jupyter/nb2kg) server extension is used to connect a Notebook from a local desktop or laptop to the Enterprise Gateway instance.  Please refer to the NB2KG repository's README file for [installation instructions](https://github.com/jupyter/nb2kg#install).

Extending the notebook launch command listed on the [NB2KG repo](https://github.com/jupyter/nb2kg#run-notebook-server), one might use the following...

```bash
export KG_URL=http://<ENTERPRISE_GATEWAY_HOST_IP>:8888
export KG_HTTP_USER=guest
export KG_HTTP_PASS=guest-password
export KERNEL_USERNAME=${KG_HTTP_USER}
jupyter notebook \
  --NotebookApp.session_manager_class=nb2kg.managers.SessionManager \
  --NotebookApp.kernel_manager_class=nb2kg.managers.RemoteKernelManager \
  --NotebookApp.kernel_spec_manager_class=nb2kg.managers.RemoteKernelSpecManager
```

For your convenience, we have also built a docker image ([elyra/nb2kg](docker.html#elyra-nb2kg)) with Jupyter Notebook, Jupyter Lab and NB2KG which can be launched by the command below:

```bash
docker run -t --rm \
  -e KG_URL='http://<master ip>:8888' \
  -e KG_HTTP_USER=guest \
  -e KG_HTTP_PASS=guest-password \
  -e VALIDATE_KG_CERT='false' \
  -e LOG_LEVEL=DEBUG \
  -p 8888:8888 \
  -v ${HOME}/notebooks/:/tmp/notebooks \
  -w /tmp/notebooks \
  elyra/nb2kg
```

Notebook files residing in `${HOME}/notebooks` can then be accessed via `http://localhost:8888`.  

To invoke Jupyter Lab, simply add `lab` to the endpoint: `http://localhost:8888/lab`
