## Getting started

This document describes some of the basics of installing and running Jupyter Enterprise Gateway.

### Using pip

We upload stable releases of Jupyter Enterprise Gateway to PyPI. You can use `pip` to install the 
latest version along with its dependencies.

```bash
# install from pypi
pip install jupyter_enterprise_gateway
```

Once installed, you can use the `jupyter` CLI to run the server.

```bash
# run it with default options
jupyter enterprisegateway
```

### Using conda

You can install Jupyter Enterprise Gateway using conda as well.

```bash
conda install -c conda-forge jupyter_enterprise_gateway
```

Once installed, you can use the `jupyter` CLI to run the server as shown above.

### Using a docker-stacks image

You can add the enterprise gateway to any [docker-stacks](https://github.com/jupyter/docker-stacks) 
image by writing a Dockerfile patterned after the following example:

```bash
# start from the jupyter image with R, Python, and Scala (Apache Toree) kernels pre-installed
FROM jupyter/all-spark-notebook

# install elyra
RUN pip install jupyter_enterprise_gateway

# run jupyter elyra on container start, not notebook server
EXPOSE 8888
CMD ["jupyter", "enterprisegateway", "--ip=0.0.0.0", "--port=8888"]
```

You can then build and run it.

```bash
docker build -t my/enterprise-gateway .
docker run -it --rm -p 8888:8888 my/enterprise-gateway
```

### Enterprise Installation
Jupyter Enterprise Gateway is intended to be installed on a Kerberized HDP cluster with Spark2 and 
Yarn services installed and running. To support Scala kernels, Apache Toree must be installed. 
To support IPython kernels and R kernels to run on Yarn worker nodes, various packages have 
to be installed on each Yarn worker node. The commands below may have to be customized to specific 
cluster environments.

#### Installing Enterprise Gateway
Enterprise Gateway is typically installed on a cluster node with a public IP address. The following 
commands have been verified to work on a cluster with HDP 2.6.1 installed on RHEL 7.3.

Run the following commands on the "public" node of the cluster:
```Bash
EG_DOWNLOAD_SERVER="9.30.252.137"

SPARK_HOME="${SPARK_HOME:-/usr/hdp/current/spark2-client}"    # HDP

TOREE_PIP_INSTALL_PACKAGE="http://${EG_DOWNLOAD_SERVER}/dist/toree/toree-0.2.0.dev1.tar.gz"

yum install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
yum install -y \
    git \
    libcurl-devel.x86_64 \
    openssl-devel.x86_64 \
    python2-cryptography.x86_64 \
    python2-pip.noarch \
    R

python -m pip install --upgrade --force pip

pip install --upgrade http://${EG_DOWNLOAD_SERVER}/dist/elyra/jupyter_enterprise_gateway-0.0.2.dev0-py2.py3-none-any.whl

################################################################################

# pip-install the Apache Toree installer
pip install "${TOREE_PIP_INSTALL_PACKAGE}"

# install a new Toree Scala kernel which will be updated with Enterprise Gateway's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.1" --interpreters="Scala"

# set a few helper variables
EG_DEV_FOLDER="$(pip list 2> /dev/null | grep -o '/.*/enterprise-gateway')"
SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"
KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

# rename the Toree Scala kernel we just installed
mv "${SCALA_KERNEL_DIR}" "${KERNELS_FOLDER}/spark_2.1_scala_yarn_cluster"

# overwrite Toree's kernel files and create remaining kernels from Enterprise Gateway (including Toree Scala, IPython, R)
yes | cp -r "${EG_DEV_FOLDER}/etc/kernels"/* "${KERNELS_FOLDER}/"

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

#### Starting Enterprise Gateway

Create a script to start Enterprise Gateway, `start_jeg.sh`, replace the variables that are flagged 
with `TODO: `:

```Bash
#!/bin/bash

# TODO: chose SPARK_HOME based on your cluster installation (TODO: update for your cluster)
export SPARK_HOME="${SPARK_HOME:-/usr/hdp/current/spark2-client}"

CLUSTER_NAME=$(hostname | sed -e 's/[0-9].fyre.ibm.com//')

# TODO: specify Yarn ResourceManager node, here it is on node 2 (TODO: update for your cluster)
export EG_YARN_ENDPOINT=http://${CLUSTER_NAME}2.fyre.ibm.com:8088/ws/v1/cluster

# TODO: specify Yarn worker nodes, here they are node 3 and node 4 (TODO: update for your cluster)
export EG_REMOTE_HOSTS=${CLUSTER_NAME}3,${CLUSTER_NAME}4

#export EG_REMOTE_USER=spark
#export EG_REMOTE_PWD=""
#export EG_TEST_BLOCK_LAUNCH=0.0

export EG_PROXY_LAUNCH_LOG=/tmp/proxy_launch.log

# launching kernels on Yarn may take longer than the default of 20 seconds
export EG_KERNEL_LAUNCH_TIMEOUT=40

#export EG_CONNECTION_FILE_MODE=socket

START_CMD="jupyter enterprisegateway --ip=0.0.0.0 --port=8888 --port_retries=0 --log-level=DEBUG --MappingKernelManager.cull_idle_timeout=3600 --MappingKernelManager.cull_interval=60 --JupyterWebsocketPersonality.list_kernels=True"

LOG=~/jeg.log
PIDFILE=~/jeg.pid

eval "$START_CMD > $LOG 2>&1 &"
if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```
It will start Enterprise Gateway in the background.
 - to follow the log output, run `tail -F jeg.log` 
 - to stop Enterprise Gateway, run `kill $(cat ~/jeg.pid)`


#### Connecting a Notebook Client to Enterprise Gateway
[NB2KG](https://github.com/jupyter/kernel_gateway_demos/tree/master/nb2kg) is used to connect from a 
local desktop or laptop to the Enterprise Gateway instance on the Yarn cluster. The most convenient 
way to use a pre-configured installation of NB2KG would be using the Docker image 
[biginsights/jupyter-nb-nb2kg:dev](https://hub.docker.com/r/biginsights/jupyter-nb-nb2kg/). Replace 
the `<ENTERPRISE_GATEWAY_HOST_IP>` in the command below:
```Bash
docker run -t --rm \
    -e KG_URL='http://<ENTERPRISE_GATEWAY_HOST_IP>:8888' \
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