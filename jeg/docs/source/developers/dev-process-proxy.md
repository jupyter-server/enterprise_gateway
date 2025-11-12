# Implementing a process proxy

A process proxy implementation is necessary if you want to interact with a resource manager that is not currently supported or extend some existing behaviors. For example, recently, we've had [contributions](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/enterprise_gateway/services/processproxies/crd.py#L9) that interact with [Kubernetes Custom Resource Definitions](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/#customresourcedefinitions), which is an example of _extending_ the `KubernetesProcessProxy` to accomplish a slightly different task.

Examples of resource managers in which there's been some interest include [Slurm Workload Manager](https://slurm.schedmd.com/documentation.html) and [Apache Mesos](https://mesos.apache.org/), for example. In the end, it's really a matter of having access to an API and the ability to apply "tags" or "labels" in order to _discover_ where the kernel is running within the managed cluster. Once you have that information, then it becomes of matter of implementing the appropriate methods to control the kernel's lifecycle.

```{admonition} Important!
:class: error

Before continuing, it is important to consider timeframes here.  You may instead want to implement a [_Kernel Provisioner_](https://jupyter-client.readthedocs.io/en/latest/provisioning.html) rather an a Process Proxy since _provisioners_ are available to the general framework!

The [Enterprise Gateway 4.0 release is slated to adopt Kernel Provisioners](../contributors/roadmap.md) but must remain on a down-level `jupyter_client` release (< 7.x) until that time as Enterprise Gateway (and process proxies) are currently incompatible.

That said, if you and your organization plan to stay on Enterprise Gateway 2.x or 3.x for the next couple years, then implementing a process proxy may be in your best interest.  Fortunately, the two constructs are nearly identical since Kernel Provisioners are essentially Process Proxies _properly_ integrated into the Jupyter framework thereby eliminating the need for various `KernelManager` hooks.
```

## General approach

Please refer to the [Process Proxy section](../contributors/system-architecture.md#process-proxy) in the System Architecture pages for descriptions and structure of existing process proxies. Here is the general guideline for the process of implementing a process proxy.

1. Identify and understand how to _decorate_ your "job" within the resource manager. In Hadoop YARN, this is done by using the kernel's ID as the _application name_ by setting the [`--name` parameter to `${KERNEL_ID}`](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/etc/kernelspecs/spark_python_yarn_cluster/kernel.json#L14). In Kubernetes, we apply the kernel's ID to the [`kernel-id` label on the POD](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml.j2#L16).
1. Today, all invocations of kernels into resource managers use a shell or python script mechanism configured into the `argv` stanza of the kernelspec. If you take this approach, you need to apply the necessary changes to integrate with your resource manager.
1. Determine how to interact with the resource manager's API to _discover_ the kernel and determine on which host it's running. This interaction should occur immediately following Enterprise Gateway's receipt of the kernel's connection information in its response from the kernel launcher. This extra step, performed within `confirm_remote_startup()`, is necessary to get the appropriate host name as reflected in the resource manager's API.
1. Determine how to monitor the "job" using the resource manager API. This will become part of the `poll()` implementation to determine if the kernel is still running. This should be as quick as possible since it occurs every 3 seconds. If this is an expensive call, you may need to make some adjustments like skip the call every so often.
1. Determine how to terminate "jobs" using the resource manager API. This will become part of the termination sequence, but probably only necessary if the message-based shutdown does not work (i.e., a last resort).

```{tip}
Because kernel IDs are globally unique, they serve as ideal identifiers for discovering where in the cluster the kernel is running.
```

You will likely need to provide implementations for `launch_process()`, `poll()`, `wait()`, `send_signal()`, and `kill()`, although, depending on where your process proxy resides in the class hierarchy, some implementations may be reused.

For example, if your process proxy is going to service remote kernels, you should consider deriving your implementation from the [`RemoteProcessProxy` class](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/enterprise_gateway/services/processproxies/processproxy.py#L981). If this is the case, then you'll need to implement `confirm_remote_startup()`.

Likewise, if your process proxy is based on containers, you should consider deriving your implementation from the [`ContainerProcessProxy`](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/enterprise_gateway/services/processproxies/container.py#L34). If this is the case, then you'll need to implement `get_container_status()` and `terminate_container_resources()` rather than `confirm_remote_startup()`, etc.

Once the process proxy has been implemented, construct an appropriate kernel specification that references your process proxy and iterate until you are satisfied with how your remote kernels behave.
