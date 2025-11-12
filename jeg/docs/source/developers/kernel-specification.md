# Implementing a kernel specification

If you find yourself [implementing a kernel launcher](kernel-launcher.md), you'll need a way to make that kernel and kernel launcher available to applications. This is accomplished via the _kernel specification_ or _kernelspec_.

Kernelspecs reside in well-known directories. For Enterprise Gateway, we generally recommend they reside in `/usr/local/share/jupyter/kernels` where each entry in this directory is a directory representing the name of the kernel. The kernel specification is represented by the file `kernel.json`, the contents of which essentially indicate what environment variables should be present in the kernel process (via the `env` _stanza_) and which command (and arguments) should be issued to start the kernel process (via the `argv` _stanza_). The JSON also includes a `metadata` stanza that contains the process_proxy configuration, along with which process proxy class to instantiate to help manage the kernel process's lifecycle.

One approach the sample Enterprise Gateway kernel specifications take is to include a shell script that actually issues the `spark-submit` request. It is this shell script (typically named `run.sh`) that is referenced in the `argv` stanza.

Here's an example from the [`spark_python_yarn_cluster`](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernelspecs/spark_python_yarn_cluster/kernel.json) kernel specification:

```JSON
{
  "language": "python",
  "display_name": "Spark - Python (YARN Cluster Mode)",
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.yarn.YarnClusterProcessProxy"
    },
    "debugger": true
  },
  "env": {
    "SPARK_HOME": "/usr/hdp/current/spark2-client",
    "PYSPARK_PYTHON": "/opt/conda/bin/python",
    "PYTHONPATH": "${HOME}/.local/lib/python3.8/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip",
    "SPARK_OPTS": "--master yarn --deploy-mode cluster --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false --conf spark.yarn.appMasterEnv.PYTHONUSERBASE=/home/${KERNEL_USERNAME}/.local --conf spark.yarn.appMasterEnv.PYTHONPATH=${HOME}/.local/lib/python3.8/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip --conf spark.yarn.appMasterEnv.PATH=/opt/conda/bin:$PATH ${KERNEL_EXTRA_SPARK_OPTS}",
    "LAUNCH_OPTS": ""
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_yarn_cluster/bin/run.sh",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}",
    "--RemoteProcessProxy.port-range",
    "{port_range}",
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "lazy"
  ]
}
```

where [`run.sh`](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernelspecs/spark_python_yarn_cluster/bin/run.sh) issues `spark-submit` specifying the kernel launcher as the "application":

```bash
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "${IMPERSONATION_OPTS}" \
     "${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}" \
     "$@"
```

For container-based environments, the `argv` may instead reference a script that is meant to create the container pod (for Kubernetes). For these, we use a [template file](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml.j2) that operators can adjust to meet the needs of their environment. Here's how that `kernel.json` looks:

```json
{
  "language": "python",
  "display_name": "Python on Kubernetes",
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy",
      "config": {
        "image_name": "elyra/kernel-py:VERSION"
      }
    },
    "debugger": true
  },
  "env": {},
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_kubernetes.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.port-range",
    "{port_range}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```

When using the `launch_ipykernel` launcher (aka the Python kernel launcher), subclasses of `ipykernel.kernelbase.Kernel` can be launched. By default, this launcher uses the classname `"ipykernel.ipkernel.IPythonKernel"`, but other subclasses of `ipykernel.kernelbase.Kernel` can be specified by adding a `--kernel-class-name` parameter to the `argv` stanza. See [Invoking subclasses of `ipykernel.kernelbase.Kernel`](kernel-launcher.md#invoking-subclasses-of-ipykernelkernelbasekernel) for more information.

As should be evident, kernel specifications are highly tuned to the runtime environment so your needs may be different, but _should_ resemble the approaches we've taken so far.
