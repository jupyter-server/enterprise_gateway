# Jupyter Elyra

[![Google Group](https://img.shields.io/badge/-Google%20Group-lightgrey.svg)](https://groups.google.com/forum/#!forum/jupyter) 
[![PyPI version](https://badge.fury.io/py/jupyter_elyra.svg)](https://badge.fury.io/py/jupyter_elyra) 
[![Build Status](https://travis-ci.org/jupyter-incubator/dashboards.svg?branch=master)](https://travis-ci.org/jupyter/elyra)
[![Code Health](https://landscape.io/github/jupyter/elyra/master/landscape.svg?style=flat)](https://landscape.io/github/jupyter/elyra/master)
[![Documentation Status](http://readthedocs.org/projects/jupyter-elyra/badge/?version=latest)](https://jupyter-kernel-gateway.readthedocs.io/en/latest/?badge=latest)

## Overview

Jupyter Elyra is ...

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

## Contributing

The [Development page](https://jupyter-elyra.readthedocs.io/en/latest/devinstall.html) includes information about setting up a development environment and typical developer tasks.

## Elyra Details


Below are sections presenting details of the Elyra internals and other related items.  While we will attempt to maintain its consistency, the ultimate answers are in the code itself.

## Elyra Process Proxy Extensions
Elyra is follow-on project to Jupyter Kernel Gateway with additional abilities to support remote kernel sessions on behalf of multiple users within resource managed frameworks such as Yarn.  Elyra introduces these capabilities by extending the existing class hierarchies for `KernelManager`, `MultiKernelManager` and `KernelSpec` classes, along with an additional abstraction known as a *process proxy*.

### Overview
At its basic level, a running kernel consists of two components for its communication - a set of ports and a process.

**Kernel Ports**

The first component is a set of five zero-MQ ports used to convey the Jupyter protocol between the Notebook and the underlying kernel.  In addition to the 5 ports, is an IP address, a key, and a signature scheme indicator used to interpret the key.  These eight pieces of information are conveyed to the kernel via a json file, known as the connection file. 

In today's JKG implementation, the IP address must be a local IP address meaning that the kernel cannot be remote from the kernel gateway.  The enforcement of this restriction is down in the jupyter_client module - two levels below JKG.

This component is the core communication mechanism between the Notebook and the kernel.  All aspects, including life-cycle management, can occur via this component.  The kernel process (below) comes into play only when port-based communication becomes unreliable or additional information is required.

**Kernel Process**

When a kernel is launched, one of the fields of the kernel's associated kernel specification is used to identify a command to invoke.  In today's implementation, this command information, along with other environment variables (also described in the kernel specification), is passed to `popen()` which returns a process class.  This class supports four basic methods following its creation:
1. `poll()` to determine if the process is still running
2. `wait()` to block the caller until the process has terminated
3. `send_signal(signum)` to send a signal to the process 
4. `kill()` to terminate the process

As you can see, other forms of process communication can be achieved by abstracting the launch mechanism.

### Remote Kernel Spec
The primary vehicle for indicating a given kernel should be handled in a different manner is the kernel specification, otherwise known as the *kernel spec*.  Elyra introduces a new subclass of KernelSpec named `RemoteKernelSpec`.  

The `RemoteKernelSpec` class provides support for a new (and optional) stanza within the kernelspec file.  This stanza is named `process_proxy` and identifies the class that provides the kernel's process abstraction (while allowing for future extensions).

Here's an example of a kernel specification that uses the `DistributedProcessProxy` class for its abstraction:
```json
{
  "language": "scala",
  "display_name": "Spark 2.1 - Scala (YARN Client Mode)",
  "process_proxy": {
    "class_name": "elyra.services.processproxies.distributed.DistributedProcessProxy"
  },
  "env": {
    "SPARK_HOME": "/usr/hdp/current/spark2-client",
    "__TOREE_SPARK_OPTS__": "--master yarn --deploy-mode client --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID}",
    "__TOREE_OPTS__": "",
    "LAUNCH_OPTS": "",
    "DEFAULT_INTERPRETER": "Scala"
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_2.1_scala_yarn_client/bin/run.sh",
    "--profile",
    "{connection_file}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
}
```

The `RemoteKernelSpec` class definition can be found in [remotekernelspec.py](https://github.com/SparkTC/elyra/blob/elyra/elyra/services/kernelspecs/remotekernelspec.py)

See the [Process Proxy](#process-proxy) section for more details.

### Remote Mapping Kernel Manager
`RemoteMappingKernelManager` is a subclass of JKG's existing `SeedingMappingKernelManager` and provides two functions.
1. It provides the vehicle for making the `RemoteKernelManager` class known and available.
2. It overrides `start_kernel` to look at the target kernel's kernel spec to see if it contains a remote process proxy class entry.  If so, it records the name of the class in its member variable to be made avaiable to the kernel start logic.

### Remote Kernel Manager
`RemoteKernelManager` is a subclass of JKG's existing `KernelGatewayIOLoopKernelManager` class and provides the primary integration points for remote process proxy invocations.  It implements a number of methods which allow Elyra to circumvent functionality that might otherwise be prevented.  As a result, some of these overrides may not be necessary if lower layers of the Jupyter framework were modified.  For example, some methods are required because Jupyter makes assumptions that the kernel process is local.

Its primary functionality, however, is to override the `_launch_kernel` method (which is the method closest to the process invocation) and instantiates the appropriate process proxy instance - which is then returned in place of the process instance used in today's implementation.  Any interaction with the process then takes place via the process proxy.

Both `RemoteMappingKernelManager` and `RemoteKernelManager` class definitions can be found in [remotemanager.py](https://github.com/SparkTC/elyra/blob/elyra/elyra/services/kernels/remotemanager.py)

### Process Proxy
Process proxy classes derive from the abstract base class `BaseProcessProxyABC` - which defines the four basic process methods.  There are two immediate subclasses of `BaseProcessProxyABC` - `LocalProcessProxy` and `RemoteProcessProxy`.  

`LocalProcessProxy` is essentially a pass-through to the current implementation.  KernelSpecs that do not contain a `process_proxy` stanza will use `LocalProcessProxy`.  

`RemoteProcessProxy` is an abstract base class representing remote kernel processes.  Currently, there are two built-in subclasses of `RemoteProcessProxy` - `DistributedProcessProxy` - representing a proof of concept class that remotes a kernel via ssh and `YarnClusterProcessProxy` - representing the design target of launching kernels hosted as yarn applications via yarn/cluster mode.  These class definitions can be found in [processproxies package](https://github.com/SparkTC/elyra/blob/elyra/elyra/services/processproxies).

The constructor signature looks as follows:

```python
def __init__(self, kernel_manager):
```

where 
* `kernel_manager` is an instance of a `RemoteKernelManager` class that is associated with the corresponding `RemoteKernelSpec` instance.

```python
@abstractmethod
def launch_process(self, kernel_cmd, *kw):
```
where
* `kernel_cmd` is a list (argument vector) that should be invoked to launch the kernel.  This parameter is an artifact of the kernel manager `_launch_kernel()` method.  
* `**kw` is a set key-word arguments. 

The `launch_process()` method is the primary method exposed on the Process Proxy classes.  It's responsible for performing the appropriate actions relative to the target type.  The process must be in a running state prior to returning from this method - otherwise attempts to use the connections will not be successful since the (remote) kernel needs to have created the sockets.

All process proxy subclasses classes should ensure `BaseProcessProxyABC.launch_process()` is called - which will automatically place a variable named `KERNEL_ID` (consisting of the kernel's unique ID) into the corresponding kernel's environment variable list since `KERNEL_ID` is a primary mechanism for associating remote applications to a specific kernel instance.

```python
def poll(self):
```
The `poll()` method is used by the Jupyter framework to determine if the process is still alive.  By default, the framework's heartbeat mechanism calls `poll()` every 3 seconds.  This value can be adjusted via the configuration setting [`KernelRestarter.time_to_dead`](http://jupyter-console.readthedocs.io/en/latest/config_options.html).

This method returns `None` if the process is still running, `False` otherwise (per the `popen()` contract).

```python
def wait(self):
```
The `wait()` method is used by the Jupyter framework when terminating a kernel.  Its purpose is to block return to the caller until the process has terminated.  Since this could be a while, its best to return control in a reasonable amount of time since the kernel instance is destroyed anyway. This method does not return a value.

```python
def send_signal(self, signum):
```
The `send_signal()` method is used by the Jupyter framework to send a signal to the process.  Currently, `SIGINT (2)` (to interrupt the kernel) is the signal sent.

It should be noted that for normal processes - both local and remote - `poll()` and `kill()` functionality can be implemented via `send_signal` with `signum` values of `0` and `9`, respectively.

This method returns `None` if the process is still running, `False` otherwise.   

```python
def kill(self):
```
The `kill()` method is used by the Jupyter framework to terminate the kernel process.  This method is only necessary when the request to shutdown the kernel - sent via the control port of the zero-MQ ports - does not respond in an appropriate amount of time.

This method returns `None` if the process is killed successfully, `False` otherwise.

#### RemoteProcessProxy
As noted above, `RemoteProcessProxy` is an abstract base class that derives from `BaseProcessProxyABC`.  Subclasses of `RemoteProcessProxy` must implement two methods - `confirm_remote_startup()` and `handle_timeout()`:
```python
@abstractmethod
def confirm_remote_startup(self, kernel_cmd, **kw):
```
where
* `kernel_cmd` is a list (argument vector) that should be invoked to launch the kernel.  This parameter is an artifact of the kernel manager `_launch_kernel()` method.  
* `**kw` is a set key-word arguments. 

`confirm_remote_startup()` is responsible for detecting that the remote kernel has been appropriately launched and is ready to receive requests.  This can include gather application status from the remote resource manager but is really a function of having received the connection information from the remote kernel launcher.  (See [Launchers](#launchers))

```python
@abstractmethod
def handle_timeout(self):
```

`handle_timeout()` is responsible for detecting that the remote kernel has failed to startup in an acceptable time.  It should be called from `confirm_remote_startup()`.  If the timeout expires, `handle_timeout()` should throw HTTP Error 500 (`Internal Server Error`).

Kernel launch timeout expiration is expressed via the environment variable `KERNEL_LAUNCH_TIMEOUT`.  If this value does not exist, it defaults to the Elyra process environment variable `ELYRA_KERNEL_LAUNCH_TIMEOUT` - which defaults to 30 seconds if unspecified.  Since all `KERNEL_` environment variables "flow" from `NB2KG`, the launch timeout can be specified as a client attribute of the Notebook session.

### Launchers
As noted above a kernel is considered started once the launcher has conveyed its connection information back to the Elyra server process. Conveyance of connection information from a remote kernel is the responsibility of the remote kernel _launcher_.

Launchers provide a means of normalizing behaviors across kernels while avoiding kernel modifications.  Besides providing a location where connection file creation can occur, they also provide a 'hook' for other kinds of behaviors - like establishing virtual environments or sandboxes, providing collaboration behavior, etc.

There are three primary tasks of a launcher:
1. Creation of the connection file on the remote (target) system
2. Conveyance of the connection information back to the Elyra process
3. Invocation of the target kernel

Launchers are minimally invoked with two parameters (both of which are conveyed by the `argv` stanza of the corresponding kernel.json file) - a path to the **_non-existent_** connection file represented by the placeholder `{connection_file}` and a response address consisting of the Elyra server IP and port on which to return the connection information similarly represented by the placeholder `{response_address}`.  

Depending on the target kernel, the connection file parameter may or may not be identified by an argument name.  However, the response address is identified by the parameter `--RemoteProcessProxy.response_address`.  Its value (`{response_address}`) consists of a string of the form `<IPV4:port>` where the IPV4 address points back to the Elyra server - which is listening for a response on the provided port.

Here's a [kernel.json](https://github.com/SparkTC/elyra/blob/elyra/etc/kernels/spark_2.1_python_yarn_cluster/kernel.json) file illustrating these parameters...

```json
{
  "language": "python",
  "display_name": "Spark 2.1 - Python (YARN Cluster Mode)",
  "process_proxy": {
    "class_name": "elyra.services.processproxies.yarn.YarnClusterProcessProxy"
  },
  "env": {
    "SPARK_HOME": "/usr/hdp/current/spark2-client",
    "SPARK_OPTS": "--master yarn --deploy-mode cluster --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false",
    "LAUNCH_OPTS": ""
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_2.1_python_yarn_cluster/bin/run.sh",
    "{connection_file}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
}
```
Kernel.json files also include a `LAUNCH_OPTS:` section in the `env` stanza to allow for custom parameters to be conveyed in the launcher's environment.  `LAUNCH_OPTS` are then referenced in the [run.sh](https://github.com/SparkTC/elyra/blob/elyra/etc/kernels/spark_2.1_python_yarn_cluster/bin/run.sh) script as the initial arguments to the launcher (see [launch_ipykernel.py](https://github.com/SparkTC/elyra/blob/elyra/etc/kernels/spark_2.1_python_yarn_cluster/scripts/launch_ipykernel.py)) ...
```bash
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}" \
     "$@"
```

### Extending Elyra
Theoretically speaking, enabling a kernel for use in other frameworks amounts to the following:
1. Build a kernel specification file that identifies the process proxy class to be used.
2. Implement the process proxy class such that it supports the four primitive functions of `poll()`, `wait()`, `send_signal(signum)` and `kill()` along with `launch_process()`.  
3. If the process proxy corresponds to a remote process, derive the process proxy class from `RemoteProcessProxy` and implement `confirm_remote_startup()` and `handle_timeout()`.
4. Insert invocation of a launcher (if necessary) which builds the connection file and returns its contents on the `{response_address}` socket.

### Installation
Elyra is intended to be installed on a Kerberized HDP cluster with Spark2 and Yarn services installed and running. To support Scala kernels, Apache Toree must be installed. To support IPython kernels and R kernels to run on Yarn worker nodes, various packages have to be installed on each Yarn worker node. The commands below may have to customized to specific cluster environments.

#### Installing Elyra
Elyra is typically installed on a cluster node with a public IP address. The following commands have been verified to work on a cluster with HDP 2.6.1 installed on RHEL 7.3.

Run the following commands on the "public" node of the cluster:
```Bash
ELYRA_DOWNLOAD_SERVER="9.30.252.137"

SPARK_HOME="${SPARK_HOME:-/usr/iop/current/spark2-client}"    # IOP
SPARK_HOME="${SPARK_HOME:-/usr/hdp/current/spark2-client}"    # HDP

#TOREE_PIP_INSTALL_PACKAGE="toree"    # outdated version of Toree on pypi - Toree 0.1.0
#TOREE_PIP_INSTALL_PACKAGE="https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0/snapshots/dev1/toree-pip/toree-0.2.0.dev1.tar.gz"  # Toree 0.2.0.dev1 SNAPSHOT
TOREE_PIP_INSTALL_PACKAGE="http://${ELYRA_DOWNLOAD_SERVER}/dist/toree/toree-0.2.0.dev1.tar.gz"

NOTEBOOK_PIP_INSTALL_PACKAGE="http://${ELYRA_DOWNLOAD_SERVER}/dist/notebook/notebook-5.1.0.dev0-py2.py3-none-any.whl"

yum install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y \
    git \
    libcurl-devel.x86_64 \
    openssl-devel.x86_64 \
    python2-cryptography.x86_64 \
    python2-pip.noarch \
    R

python -m pip install --upgrade --force pip

# install customized version of the Yarn client API with support for HTTPS
pip install "git+http://github.com/lresende/yarn-client.git#egg=yarn_api_client"

################################################################################
# chose one of 3 options to install Elyra
################################################################################

# OPTION 1: install latest Elyra build from internal staging server 
pip install --upgrade http://${ELYRA_DOWNLOAD_SERVER}/dist/elyra/jupyter_kernel_gateway-2.0.0.dev-py2.py3-none-any.whl

# OPTION 2: edit-install Elyra, optionally from user fork (if USERNAME is set) and from a dev branch (if BRANCH is set)
#pip install --upgrade --src="pip_src" -e "git+https://github.com/${USERNAME:-SparkTC}/elyra.git@${BRANCH:-elyra}#egg=jupyter-kernel-gateway"

# OPTION 3: clone Elyra repo to local folder (set ELYRA_DEV_FOLDER, default: elyra) and do a pip edit-install from that
#git clone "https://github.com/${USERNAME:-SparkTC}/elyra.git" --branch "${BRANCH:-elyra}" "${ELYRA_DEV_FOLDER:-elyra}"
#pip install -e "${ELYRA_DEV_FOLDER:-elyra}"

################################################################################

# pip-install the Apache Toree installer
pip install "${TOREE_PIP_INSTALL_PACKAGE}"

# install a new Toree Scala kernel which will be updated with Elyra's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.1" --interpreters="Scala"

# set a few helper variables
ELYRA_DEV_FOLDER="$(pip list 2> /dev/null | grep -o '/.*/jupyter-kernel-gateway')"
SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"
KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

# rename the Toree Scala kernel we just installed
mv "${SCALA_KERNEL_DIR}" "${KERNELS_FOLDER}/spark_2.1_scala_yarn_cluster"

# overwrite Toree's kernel files and create remaining kernels from Elyra (including Toree Scala, IPython, R)
yes | cp -r "${ELYRA_DEV_FOLDER}/etc/kernels"/* "${KERNELS_FOLDER}/"

# if notebook version < 5.1.0 then install custom build of 5.0.0 plus kernel culling (https://github.com/jupyter/notebook/pull/2215)
pip show notebook | grep -E "Version: [6-9]|Version: 5.[1-9]" > /dev/null || pip install "${NOTEBOOK_PIP_INSTALL_PACKAGE}"

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
export SPARK_HOME="${SPARK_HOME:-/usr/iop/current/spark2-client}"
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

export JUPYTER_DATA_DIR=/tmp      # /var/lib/elyra
export JUPYTER_RUNTIME_DIR=/tmp   # /var/run/elyra/runtime

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

