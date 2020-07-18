## Spark Standalone

By default, Jupyter Enterprise Gateway provides feature parity with Jupyter Kernel Gateway's websocket-mode, which means that by installing kernels in Enterprise Gateway and using the vanilla kernelspecs created during installation you will have your kernels running in client mode with drivers running on the same host as Enterprise Gateway.

Having said that, even if you are not leveraging the full distributed capabilities of Jupyter Enterprise Gateway, client mode can still help mitigate resource starvation by enabling a pseudo-distributed mode, where kernels are started in different nodes of the cluster utilizing a round-robin algorithm. In this case, you can still experience bottlenecks on a given node that receives requests to start "large" kernels, but otherwise, you will be better off compared to when all kernels are started on a single node or as local processes, which is the default for vanilla Jupyter Notebook.

The pseudo-distributed capabilities are currently supported in Spark Standalone and require the following environment variables to be set:

* SPARK_HOME: Must point to the Apache Spark installation path

```
SPARK_HOME:/usr/hdp/current/spark2-client                            #For HDP distribution
```

* EG_REMOTE_HOSTS must be set to a comma-separated set of FQDN hosts indicating the hosts available for running kernels. (This can be specified via the command line as well: `--EnterpriseGatewayApp.remote_hosts`)

```
EG_REMOTE_HOSTS=elyra-node-1.fyre.ibm.com,elyra-node-2.fyre.ibm.com,elyra-node-3.fyre.ibm.com,elyra-node-4.fyre.ibm.com,elyra-node-5.fyre.ibm.com
```

### Configuring Kernels for Spark Standalone

Although Enterprise Gateway does not currently provide sample kernelspecs for Spark standalone, here are the steps necessary to convert a yarn_client kernelspec to standalone.

For each supported Jupyter Kernel, we have provided sample kernel configurations and launchers as part of the release
[jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz](https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz).

Considering we would like to enable the IPython Kernel that comes pre-installed with Anaconda to run on
Spark Standalone, we would have to copy the sample configuration folder **spark_python_yarn_client**
to where the Jupyter kernels are installed (e.g. jupyter kernelspec list) and rename it to **spark_python_spark_standalone***

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz
SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "python3" | awk '{print $2}')"
KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"
tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_client/ spark_python_yarn_client/
mv $KERNELS_FOLDER/spark_python_yarn_client $KERNELS_FOLDER/spark_python_spark_standalone
```

You need to edit the kernel.json:

+ Update the display_name with e.g. `Spark - Python (Spark Standalone)`.
+ Update the `--master` option in the SPARK_OPTS to point to the spark master node rather than indicate `--deploy-mode client`.
+ Update `SPARK_OPTS` and remove the `spark.yarn.submit.waitAppCompletion=false`.

After that, you should have a kernel.json that looks similar to the one below:

```json
{
  "language": "python",
  "display_name": "Spark - Python (Spark Standalone)",
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.distributed.DistributedProcessProxy"
    }
  },
  "env": {
    "SPARK_HOME": "/usr/hdp/current/spark2-client",
    "PYSPARK_PYTHON": "/opt/conda/bin/python",
    "PYTHONPATH": "${HOME}/.local/lib/python3.6/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip",
    "SPARK_YARN_USER_ENV": "PYTHONUSERBASE=/home/yarn/.local,PYTHONPATH=${HOME}/.local/lib/python3.6/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip,PATH=/opt/conda/bin:$PATH",
    "SPARK_OPTS": "--master spark://127.0.0.1:7077  --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID}",
    "LAUNCH_OPTS": ""
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_spark_standalone/bin/run.sh",
     "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
}
```

After making any necessary adjustments such as updating SPARK_HOME or other environment specific configuration, you now should have a new Kernel available which will use Jupyter Enterprise Gateway to execute your notebook cell contents.

### Scala Kernel (Apache Toree kernel)

We have tested the latest version of [Apache Toree](http://toree.apache.org/) with Scala 2.11 support.  Please note that the Apache Toree kernel is now bundled in the kernelspecs tar file for each of the Scala kernelspecs provided by Enterprise Gateway.

Follow the steps below to install/configure the Toree kernel:

**Install Apache Toree Kernelspecs**

Considering we would like to enable the Scala Kernel to run on YARN Cluster and Client mode we would have to copy the sample configuration folder **spark_scala_yarn_client** to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz
KERNELS_FOLDER=/usr/local/share/jupyter/kernels
tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_scala_yarn_client/ spark_scala_yarn_client/
mv $KERNELS_FOLDER/spark_scala_yarn_client $KERNELS_FOLDER/spark_scala_spark_standalone
```

For more information about the Scala kernel, please visit the [Apache Toree](http://toree.apache.org/) page.

### Installing support for Python (IPython kernel)

The IPython kernel comes pre-installed with Anaconda and we have tested with its default version of [IPython kernel](http://ipython.readthedocs.io/en/stable/).

**Update the IPython Kernelspecs**

Considering we would like to enable the IPython kernel to run on YARN Cluster and Client mode we would have to copy the sample configuration folder **spark_python_yarn_client** to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz
KERNELS_FOLDER=/usr/local/share/jupyter/kernels
tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_client/ spark_python_yarn_client/
mv $KERNELS_FOLDER/spark_python_yarn_client $KERNELS_FOLDER/spark_python_spark_standalone
```

For more information about the IPython kernel, please visit the [IPython kernel](http://ipython.readthedocs.io/en/stable/) page.

### Installing support for R (IRkernel)

**Install IRkernel**

Perform the following steps on Jupyter Enterprise Gateway hosting system as well as all YARN workers

```Bash
conda install --yes --quiet -c r r-essentials r-irkernel r-argparse
# Create an R-script to run and install packages and update IRkernel
cat <<'EOF' > install_packages.R
install.packages(c('repr', 'IRdisplay', 'evaluate', 'git2r', 'crayon', 'pbdZMQ',
                   'devtools', 'uuid', 'digest', 'RCurl', 'curl', 'argparse'),
                   repos='http://cran.rstudio.com/')
devtools::install_github('IRkernel/IRkernel@0.8.14')
IRkernel::installspec(user = FALSE)
EOF
# run the package install script
$ANACONDA_HOME/bin/Rscript install_packages.R
# OPTIONAL: check the installed R packages
ls $ANACONDA_HOME/lib/R/library
```

**Update the IRkernel Kernelspecs**

Considering we would like to enable the IRkernel to run on YARN Cluster and Client mode we would have to copy the sample configuration folder **spark_R_yarn_client** to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz
KERNELS_FOLDER=/usr/local/share/jupyter/kernels
tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_R_yarn_client/ spark_R_yarn_client/
mv $KERNELS_FOLDER/spark_R_yarn_client $KERNELS_FOLDER/spark_R_spark_standalone
```

For more information about the iR kernel, please visit the [IRkernel](https://irkernel.github.io/) page.

After making any necessary adjustments such as updating SPARK_HOME or other environment specific configuration, you now should have a new Kernel available which will use Jupyter Enterprise Gateway to execute your notebook cell contents in distributed mode on a Spark/Yarn Cluster.   
