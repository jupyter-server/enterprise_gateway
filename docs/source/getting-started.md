## Getting started

Jupyter Enterprise Gateway requires Python (Python 3.3 or greater, or Python 2.7) and is intended
to be installed on a [Apache Spark 2.x](http://spark.apache.org/docs/latest/index.html) cluster.

The following Resource Managers are supported with the Jupyter Enterprise Gateway:

* YARN Resource Manager - Local Mode
* YARN Resource Manager - Cluster Mode

The following kernels have been tested with the Jupyter Enterprise Gateway:

* Python/Apache Spark 2.x with IPython kernel
* Scala 2.11/Apache Spark 2.x with Apache Toree kernel
* R/Apache Spark 2.x with IRkernel

To support Scala kernels, [Apache Toree](https://toree.apache.org/) must be installed. To support
IPython kernels and R kernels to run on the YARN containers, various packages have to be installed
on each of the YARN data nodes. The simplest way to enable all the data nodes with required
dependencies is to install [Anaconda](https://anaconda.com/) on all cluster nodes.

To take full advantage of security and user impersonation capabilities, a Kerberized cluster
is recommended.

### Installing Enterprise Gateway

For new users, we **highly recommend** [installing Anaconda](http://www.anaconda.com/download).
Anaconda conveniently installs Python, the [Jupyter Notebook]
(http://jupyter.readthedocs.io/en/latest/install.html), the [IPython kernel]
(http://ipython.readthedocs.io/en/stable/install/kernel_install.html) and other commonly used
packages for scientific computing and data science.

Use the following installation steps:

* Download [Anaconda](http://www.anaconda.com/download). We recommend downloading Anaconda’s
latest Python 3 version (currently Python 3.5).

* Install the version of Anaconda which you downloaded, following the instructions on the download
page.

* Install the latest version of Jupyter Enterprise Gateway from [PyPI](https://pypi.python.org/pypi)
using `pip`(part of Anaconda) along with its dependencies.

```bash
# install from pypi
pip install jupyter_enterprise_gateway
```

Similarly, you can use `pip uninstall jupyter_enterprise_gateway` to uninstall
Jupyter Enterprise Gateway.

At this point, the Jupyter Enterprise Gateway deployment provides local kernel support which is
fully compatible with Jupyter Kernel Gateway.


[//]: # (### Using conda)
[//]: # ( )
[//]: # (You can install Jupyter Enterprise Gateway using conda as well.)
[//]: # ( )
[//]: # (```bash)
[//]: # (conda install -c conda-forge jupyter_enterprise_gateway)
[//]: # (```)
[//]: # ( )
[//]: # (Once installed, you can use the `jupyter` CLI to run the server as shown above.)

#### Using a docker-stacks image

You can add the enterprise gateway to any [docker-stacks](https://github.com/jupyter/docker-stacks)
image by writing a `Dockerfile` patterned after the following example:

```bash
# start from the jupyter image with R, Python, and Scala (Apache Toree) kernels pre-installed
FROM jupyter/all-spark-notebook

# install Jupyter Enterprise Gateway
RUN pip install jupyter_enterprise_gateway

# run Jupyter Enterprise Gateway on container start
EXPOSE 8888
CMD ["jupyter", "enterprisegateway", "--ip=0.0.0.0", "--port=8888"]
```

You can then build the Docker image and run it as shown below:

```bash
docker build -t enterprise-gateway .
docker run -it --rm -p 8888:8888 enterprise-gateway
```

### Enabling Distributed Kernel support

To leverage the full distributed capabilities of Jupyter Enterprise Gateway, there is a need to
provide a few additional configuration options in a cluster deployment.

The distributed capabilities are currently based on a Apache Spark cluster utilizing YARN as the
Resource Manager and thus require the following environment variables to be set to facilitate the
integration between Apache Spark and YARN components:

* SPARK_HOME: Must point to the Apache Spark Master
```
SPARK_HOME:/usr/hdp/current/spark2-client                            #For HDP distribution
```

* EG_YARN_ENDPOINT: Must point to the YARN Resource Manager endpoint
```
EG_YARN_ENDPOINT=http://${YARN_NODE_MANAGER_FQDN}:8088/ws/v1/cluster #Common to YARN deployment
``` 

### Installing support for Scala (Apache Toree kernel)

We have tested the latest version of Apache Toree for Scala 2.11 support, and to enable that support, please do the following steps:


* Install Apache Toree

``` Bash
# pip-install the Apache Toree installer
pip install https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0-incubating-rc1/toree-pip/toree-0.2.0.tar.gz

# install a new Toree Scala kernel which will be updated with Enterprise Gateway's custom kernel scripts
jupyter toree install --spark_home="${SPARK_HOME}" --kernel_name="Spark 2.1" --interpreters="Scala"

```

* Update the Apache Toree Kernelspecs

We have provided some customized kernelspecs as part of the Jupyter Enterprise Gateway releases.
These kernelspecs come pre-configured with Yarn local and/or cluster mode. Please use the steps below
as an example on how to update/customize your kernelspecs.

``` Bash
wget https://github.com/SparkTC/enterprise_gateway/releases/download/v0.6/enterprise_gateway_kernelspecs.tar.gz
SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "spark_2.1_scala" | awk '{print $2}')"
KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"
tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_2.1_scala_yarn_cluster/ spark_2.1_scala_yarn_cluster/
cp $KERNELS_FOLDER/spark_2.1_scala/lib/*.jar  $KERNELS_FOLDER/spark_2.1_scala_yarn_cluster/lib
```

### Installing support for Python (IPython kernel)

The IPython kernel comes pre-configured

### Installing support for R (IRkernel)



Run the following commands on the "public" node of the cluster:
```Bash


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
Very few arguments are necessary to minimally start Enterprise Gateway.  The following command 
could be considered a minimal command:

```bash
jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0
```

where `--ip=0.0.0.0` exposes Enterprise Gateway on the public network and `--port_retries=0` ensures
that a single instance will be started.

It is recommended that you start Enterprise Gateway with
[kernel culling](http://www.spark.tc/limit-notebook-resource-consumption-by-culling-kernels/) so
as to better control kernel resources.  In addition, we recommend starting Enterprise Gateway as
a background task.  As a result, you might find it best to create a start script to maintain options,
file redirection, etc.

The following script starts Enterprise Gateway with `DEBUG` tracing enabled (default is `INFO`) and idle
kernel culling for any kernels idle for 12 hours where idle check intervals occur every minute.  The Enterprise
Gateway log can then be monitored via `tail -F enterprise_gateway.log` and it can be stopped via `kill $(cat enterprise_gateway.pid)`

```bash
#!/bin/bash

START_CMD="jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG --MappingKernelManager.cull_idle_timeout=43200 --MappingKernelManager.cull_interval=60 --MappingKernelManager.cull_connected=True"

LOG=~/enterprise_gateway.log
PIDFILE=~/enterprise_gateway.pid

eval "$START_CMD > $LOG 2>&1 &"
if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```


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
