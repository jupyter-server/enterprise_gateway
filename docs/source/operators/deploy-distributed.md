# Distributed deployments

This section describes how to deploy Enterprise Gateway to manage kernels across a distributed set of hosts. In this case, a resource manager is not used, but, rather, SSH is used to distribute the kernels. This functionality is accomplished via the [`DistributedProcessProxy`](../contributors/system-architecture.md#distributedprocessproxy).

Steps required to complete deployment on a distributed cluster are:

1. [Install Enterprise Gateway](installing-eg.md) on the "primary node" of the cluster.
1. [Install the desired kernels](installing-kernels.md)
1. Install and configure the server and desired kernel specifications (see below)
1. [Launch Enterprise Gateway](launching-eg.md)

The `DistributedProcessProxy` simply uses a fixed set of host names and selects the _next_ host using a simple round-robin algorithm (see the [Roadmap](../contributors/roadmap.md) for making this pluggable). In this case, you can still experience bottlenecks on a given node that receives requests to start "large" kernels, but otherwise, you will be better off compared to when all kernels are started on a single node or as local processes, which is the default for Jupyter Notebook and JupyterLab when not configured to use Enterprise Gateway.

The following sample kernelspecs are configured to use the `DistributedProcessProxy`:

- python_distributed
- spark_python_yarn_client
- spark_scala_yarn_client
- spark_R_yarn_client

```{admonition} Important!
:class: warning
The `DistributedProcessProxy` utilizes SSH between the Enterprise Gateway server and the remote host.  As a result, you must ensure passwordless SSH is configured between hosts.
```

The set of remote hosts used by the `DistributedProcessProxy` are derived from two places.

- The configuration option `EnterpriseGatewayApp.remote_hosts`, whose default value comes from the env variable EG_REMOTE_HOSTS - which, itself, defaults to 'localhost'.
- The config option can be [overridden on a per-kernel basis](config-kernel-override.md#per-kernel-configuration-overrides) if the process_proxy stanza contains a config stanza where there's a `remote_hosts` entry. If present, this value will be used instead.

```{tip}
Entries in the remote hosts configuration should be fully qualified domain names (FQDN). For example, `host1.acme.com, host2.acme.com`
```

```{admonition} Important!
:class: warning
All the kernel *specifications* configured to use the `DistributedProcessProxy` must be on all nodes to which there's a reference in the remote hosts configuration!  With YARN cluster node, only the Python and R kernel _packages_ are required on each node, not the entire kernel specification.
```

The following installs the sample `python_distributed` kernel specification relative to the 3.2.3 release on the given node. This step must be repeated for each node and each kernel specification.

```Bash
wget https://github.com/jupyter-server/enterprise_gateway/releases/download/v3.2.3/jupyter_enterprise_gateway_kernelspecs-3.2.3.tar.gz
KERNELS_FOLDER=/usr/local/share/jupyter/kernels
tar -zxvf jupyter_enterprise_gateway_kernelspecs-3.2.3.tar.gz --strip 1 --directory $KERNELS_FOLDER/python_distributed/ python_distributed/
```

```{tip}
You may find it easier to install all kernel specifications on each node, then remove directories corresponding to specification you're not interested in using.
```

## Specifying a load-balancing algorithm

Jupyter Enterprise Gateway provides two ways to configure how kernels are distributed across the configured set of hosts: round-robin or least-connection.

### Round-robin

The round-robin algorithm simply uses an index into the set of configured hosts, incrementing the index on each kernel startup so that it points to the next host in the configured set. To specify the use of round-robin, use one of the following:

_Command-line_:

```bash
--EnterpriseGatewayApp.load_balancing_algorithm=round-robin
```

_Configuration_:

```python
c.EnterpriseGatewayApp.load_balancing_algorithm="round-robin"
```

_Environment_:

```bash
export EG_LOAD_BALANCING_ALGORITHM=round-robin
```

Since _round-robin_ is the default load-balancing algorithm, this option is not necessary.

### Least-connection

The least-connection algorithm tracks the hosts that are currently servicing kernels spawned by the Enterprise Gateway instance. Using this information, Enterprise Gateway selects the host with the least number of kernels. It does not consider other information, or whether there is _another_ Enterprise Gateway instance using the same set of hosts. To specify the use of least-connection, use one of the following:

_Command-line_:

```bash
--EnterpriseGatewayApp.load_balancing_algorithm=least-connection
```

_Configuration_:

```python
c.EnterpriseGatewayApp.load_balancing_algorithm="least-connection"
```

_Environment_:

```bash
export EG_LOAD_BALANCING_ALGORITHM=least-connection
```

### Pinning a kernel to a host

A kernel's start request can specify a specific remote host on which to run by specifying that host in the `KERNEL_REMOTE_HOST` environment variable within the request's body. When specified, the configured load-balancing algorithm will be by-passed and the kernel will be started on the specified host.

## YARN Client Mode

YARN client mode kernel specifications can be considered _distributed mode kernels_. They just happen to use `spark-submit` from different nodes in the cluster but use the `DistributedProcessProxy` to manage their lifecycle.

YARN Client kernel specifications require the following environment variable to be set within their `env` entries:

- `SPARK_HOME` must point to the Apache Spark installation path

```
SPARK_HOME:/usr/hdp/current/spark2-client                            #For HDP distribution
```

In addition, they will leverage the aforementioned remote hosts configuration.

After that, you should have a `kernel.json` that looks similar to the one below:

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
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```

Make any necessary adjustments such as updating `SPARK_HOME` or other environment and path specific configurations.

```{tip}
Each node of the cluster will typically be configured in the same manner relative to directory hierarchies and environment variables.  As a result, you may find it easier to get kernel specifications working on one node, then, after confirming their operation, copy them to other nodes and update the remote-hosts configuration to include the other nodes.  You will still need to _install_ the kernels themselves on each node.
```

## Spark Standalone

Although Enterprise Gateway does not provide sample kernelspecs for Spark standalone, here are the steps necessary to convert a `yarn_client` kernelspec to standalone.

- Make a copy of the source `yarn_client` kernelspec into an applicable `standalone` directory.
- Edit the `kernel.json` file:
  - Update the display_name with e.g. `Spark - Python (Spark Standalone)`.
  - Update the `--master` option in the SPARK_OPTS to point to the spark master node rather than indicate `--deploy-mode client`.
  - Update `SPARK_OPTS` and remove the `spark.yarn.submit.waitAppCompletion=false`.
  - Update the `argv` stanza to reference `run.sh` in the appropriate directory.

After that, you should have a `kernel.json` that looks similar to the one below:

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
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```
