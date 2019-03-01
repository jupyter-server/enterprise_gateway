## Enabling YARN Client Mode or Spark Standalone Support

Jupyter Enterprise Gateway extends Jupyter Kernel Gateway and is 100% compatible with JKG, which means that by installing kernels in Enterprise Gateway and using the vanila kernelspecs created during installation you will have your kernels running in client mode with drivers running on the same host as Enterprise Gateway. 

Having said that, even if you are not leveraging the full distributed capabilities of Jupyter Enterprise Gateway, client mode can still help mitigate resource starvation by enabling a pseudo-distributed mode, where kernels are started in different nodes of the cluster utilizing a round-robin algorithm. In this case, you can still experience bottlenecks on a given node that receives requests to start "large" kernels, but otherwise, you will be better off compared to when all kernels are started on a single node or as local processes, which is the default for vanilla Jupyter Notebook.

The pseudo-distributed capabilities are currently supported in YARN Client mode or using vanilla Spark Standalone and require the following environment variables to be set:

* SPARK_HOME: Must point to the Apache Spark installation path
```
SPARK_HOME:/usr/hdp/current/spark2-client                            #For HDP distribution
```

* EG_REMOTE_HOSTS must be set to a comma-separated set of FQDN hosts indicating the hosts available for running kernels. (This can be specified via the command line as well: `--EnterpriseGatewayApp.remote_hosts`)

```
EG_REMOTE_HOSTS=elyra-node-1.fyre.ibm.com,elyra-node-2.fyre.ibm.com,elyra-node-3.fyre.ibm.com,elyra-node-4.fyre.ibm.com,elyra-node-5.fyre.ibm.com
```

### Configuring Kernels for YARN Client mode

For each supported Jupyter Kernel, we have provided sample kernel configurations and launchers as part of the release
[e.g. jupyter_enterprise_gateway_kernelspecs-2.0.0.dev1.tar.gz](https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0.dev1/jupyter_enterprise_gateway_kernelspecs-2.0.0.dev1.tar.gz).

Considering we would like to enable the IPython Kernel that comes pre-installed with Anaconda to run on
Yarn Client mode, we would have to copy the sample configuration folder **spark_python_yarn_client**
to where the Jupyter kernels are installed (e.g. jupyter kernelspec list)

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0.dev1/jupyter_enterprise_gateway_kernelspecs-2.0.0.dev1.tar.gz

SCALA_KERNEL_DIR="$(jupyter kernelspec list | grep -w "python3" | awk '{print $2}')"

KERNELS_FOLDER="$(dirname "${SCALA_KERNEL_DIR}")"

tar -zxvf enterprise_gateway_kernelspecs.tar.gz --strip 1 --directory $KERNELS_FOLDER/spark_python_yarn_client/ spark_python_yarn_client/

```

After that, you should have a kernel.json that looks similar to the one below:

```json
{
  "language": "python",
  "display_name": "Spark - Python (YARN Client Mode)",
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
    "SPARK_OPTS": "--master yarn --deploy-mode client --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false",
    "LAUNCH_OPTS": ""
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_yarn_client/bin/run.sh",
     "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
}
```

After making any necessary adjustments such as updating SPARK_HOME or other environment specific configuration, you now should have a new Kernel available which will use Jupyter Enterprise Gateway to execute your notebook cell contents.

### Configuring Kernels for Spark Standalone mode

The main difference between YARN Client and Standalone is the values used in SPARK_OPTS for the ```--master``` parameter.

Please see below how a kernel.json would look like for integrating with Spark Standalone:
 
 
```json
{
  "language": "python",
  "display_name": "Spark - Python (YARN Client Mode)",
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
    "SPARK_OPTS": "--master spark://127.0.0.1:7077  --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false",
    "LAUNCH_OPTS": ""
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_yarn_client/bin/run.sh",
     "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
}
```
