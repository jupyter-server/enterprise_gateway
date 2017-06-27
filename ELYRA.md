Elyra has been forked from :
https://github.com/jupyter/kernel_gateway

At the time of the fork, the last commit hash on master was:
595e34ababe24f88697968c7deb7de735760a6ae


Below are sections presenting details of the Elyra internals and other related items.  While we will attempt to maintain its consistency, the ultimate answers are in the code itself.

## Elyra Process Proxy Extensions
Elyra is Jupyter Kernel Gateway with additional abilities to support remote kernel sessions on behalf of multiple users within resource managed frameworks such as Yarn.  Elyra introduces these capabilities by extending the existing class hierarchies for `KernelManager`, `MultiKernelManager` and `KernelSpec` classes, along with an additional abstraction known as a *process proxy*.

### Overview
At its basic level, a running kernel consists of two components for its communication - a set of ports and a process.

**Kernel Ports**

The first component is a set of five zero-MQ ports used to convey the Jupyter protocol between the Notebook and the underlying kernel.  In addition to the 5 ports, is an IP address, a key, and a signature scheme indicator used to interpret the key.  These eight pieces of information are conveyed to the kernel via a json file, known as the connection file. 

In today's JKG implementation, the IP address must be a local IP address meaning that the kernel cannot be remote from the kernel gateway.  The enforcement of this restriction is down in the jupyter_client module - two levels below JKG.

This component is the core communication mechanism between the Notebook and the kernel.  All aspects, including life-cycle management, can occur via this component.  The kernel process (below) comes into play only when port-based communication becomes unreliable or additional information is required.

**Kernel Process**

When a kernel is launched, one of the fields of the kernel's associated kernel specification is used to identify a command to invoke.  In today's implementation, this command information, along with other environment variables (also described in the kernel specification), is passed to `popen` which returns a process class.  This class supports four basic methods following its creation:
1. `poll()` to determine if the process is still running
2. `wait()` to block the caller until the process has terminated
3. `send_signal(signum)` to send a signal to the process 
4. `kill()` to terminate the process

As you can see, other forms of process communication can be achieved by abstracting the launch mechanism.

### Remote Kernel Spec
The primary vehicle for indicating a given kernel should be handled in a different manner is the kernel specification, otherwise known as the *kernel spec*.  Elyra introduces a new subclass of KernelSpec named `RemoteKernelSpec`.  

The `RemoteKernelSpec` class provides support for a new (and optional) stanza within the kernelspec file.  This stanza is currently named `process_proxy` and identifies the class that provides the kernel's process abstraction along with an optional mode of conveying the connection file.

Here's an example of a kernel specification that uses the `StandaloneProcessProxy` class for its abstraction:
```json
{
  "language": "scala", 
  "display_name": "Spark 2.1 - Scala (sa)", 
  "process_proxy": {
    "class_name": "kernel_gateway.services.kernels.processproxy.StandaloneProcessProxy",
    "connection_file_mode": "push"
  },
  "env": {
    "__TOREE_SPARK_OPTS__": "--master=yarn --deploy-mode=client", 
    "SPARK_HOME": "/opt/apache/spark2-client", 
    "__TOREE_OPTS__": "", 
    "DEFAULT_INTERPRETER": "Scala", 
    "PYTHONPATH": "/opt/apache/spark2-client/python:/opt/apache/spark2-client/python/lib/py4j-0.10.4-src.zip", 
    "PYTHON_EXEC": "python"
  }, 
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_2.1_scala/bin/run.sh",
    "--profile",
    "{connection_file}"
  ]
}
```

The `RemoteKernelSpec` class definition can be found in https://github.com/SparkTC/elyra/blob/elyra/kernel_gateway/services/kernelspecs/remotekernelspec.py

See the [Process Proxy](#process-proxy) section for more details.

### Remote Mapping Kernel Manager
`RemoteMappingKernelManager` is a subclass of JKG's existing `SeedingMappingKernelManager` and provides two functions.
1. It provides the vehicle for making the `RemoteKernelManager` class known and available.
2. It overrides `start_kernel` to look at the target kernel's kernel spec to see if it contains a remote process proxy class entry.  If so, it records the name of the class in its member variable to be made avaiable to the kernel start logic.

### Remote Kernel Manager
`RemoteKernelManager` is a subclass of JKG's existing `KernelGatewayIOLoopKernelManager` class and provides the primary integration points for remote process proxy invocations.  It implements a number of methods which allow Elyra to circumvent functionality that might otherwise be prevented.  As a result, some of these overrides may not be necessary if lower layers of the Jupyter framework were modified.  For example, some methods are required because Jupyter makes assumptions that the kernel process is local.

Its primary functionality, however, is to override the `_launch_kernel` method (which is the method closest to the process invocation) and instantiates the appropriate process proxy instance - which is then returned in place of the process instance used in today's implementation.  Any interaction with the process then takes place via the process proxy.

Both `RemoteMappingKernelManager` and `RemoteKernelManager` class definitions can be found in https://github.com/SparkTC/elyra/blob/elyra/kernel_gateway/services/kernels/remotemanager.py

### Process Proxy
Process proxy classes derive from the abstract base class `BaseProcessProxyABC` - which defines the four basic process methods.  There are two built-in classes `StandaloneProcessProxy` - representing a proof of concept class that remotes a kernel via ssh but still uses yarn/client mode and `YarnProcessProxy` - representing the design target of launching kernels hosted as yarn applications via yarn/cluster mode.  These class definitions can be found in https://github.com/SparkTC/elyra/blob/elyra/kernel_gateway/services/kernels/processproxy.py

Constructors of these classes should call the `BaseProcessProxyABC` constructor - which will automatically place a variable named `KERNEL_ID` into the corresponding kernel spec's environment variable list. 

The constructor signature looks as follows:

```python
def __init__(self, kernel_manager, connection_file_mode, **kw):
```

where 
* `kernel_manager` is an instance of a `RemoteKernelManager` class that is associated with the corresponding `RemoteKernelSpec` instance.
* `connection_file_mode` is an optional string from the set {`push`, `pull`, `socket`} indicating the means by which the connection file is sent to or returned from the kernel.
* `**kw` is a set key-word arguments. The base constructor adds the `KERNEL_ID` environment variable into the dictionary located at `kw['env']`, for example.

```python
@abstractmethod
def launch_process(self, kernel_cmd, *kw):
```
where
* `kernel_cmd` is a list (argument vector) that should be invoked to launch the kernel.  This parameter is an artifact of the kernel manager `_launch_kernel()` method.  
* `**kw` is a set key-word arguments. 

The `launch_process()` method is the primary method exposed on the Process Proxy classes.  It's responsible for performing the appropriate actions relative to the target type.  The process must be in a running state prior to returning from this method - otherwise attempts to use the connections will not be successful since the (remote) kernel needs to have created the sockets.

```python
def poll(self):
```
The `poll()` method is used by the Jupyter framework to determine if the process is still alive.  By default, the framework's heartbeat mechanism calls `poll()` every 3 seconds.  As a result, if the corresponding process proxy takes time to determine the process's availability, you may want to increase the heartbeat interval.

This method returns `None` if the process is still running, `False` otherwise.   
*Note: The return value is based on the `popen()` contract.*

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

### Connection file mode and launchers
As noted above there are currently three connection file modes available: `push`, `pull`, and `socket`.  

**Push mode** is the least preferred but doesn't require any additional implementation relative to the kernel.  In this mode, the connection file (port information) is produced on the Elyra server and copied to the desired remote system.  As a result, there is a risk that the ports selected on the Elyra server will not be available when used on the remote system resulting in a failed kernel startup and requiring a restart from the client.

**Pull mode** is more preferred since it builds the connection file on the kernel's destination.  Once built, Elyra will pull the connection file back to its server and convey the connection information to the underlying classes enabling use of the kernel.  By creating the kernel at its source, the chances of port conflicts is dramatically reduced.  However, to produce the connection file, a launcher application (see below) is generally necessary - although such a mechanism has other advantages.

**Socket mode** is the most preferred.  This mode conveys the connection information back to Elyra via a socket that Elyra originally conveyed when launching the kernel via the environment variable: `KERNEL_RESPONSE_ADDRESS`.  The format of the response address is `<ip>:<port>` and will be conveyed to the launcher application via the parameter `--response-address <ip>:<port>`.  This approach is most preferred because it eliminates the need to copy a file from the remote system and the remote system sends the data - indicating that its ready.

Which modes are supported is a function of the process proxy implementation.  Currently, the `StandaloneProcessProxy` only supports `push` mode, while the `YarnProcessProxy` supports all three.

Besides the process proxy implementation, support for connection file modes is also a function of the target kernel and how it is launched.  In order to normalize behaviors across kernels, optimize connectivity and avoid kernel modifications, Elyra introduces the notion of kernel _launchers_.  

#### Launchers
As noted above, launchers provide a means of normalizing behaviors across kernels while avoiding kernel modifications.  Besides providing a location where connection file creation can occur, they also provide a 'hook' for other kinds of behaviors - like establishing virtual environments or sandboxes, providing collaboration behavior, etc.

Like the other options listed in the kernel.json env stanza, launcher options will be conveyed via the `LAUNCH_OPTS` entry as follows...

```json
  "env": {
    "SPARK_HOME": "/usr/iop/current/spark2-client",
    "SPARK_OPTS": "--master yarn --deploy-mode cluster --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --proxy-user ${KERNEL_USERNAME:-ERROR__NO__KERNEL_USERNAME}",
    "LAUNCH_OPTS": "--response-address ${KERNEL_RESPONSE_ADDRESS:-ERROR__NO__KERNEL_RESPONSE_ADDRESS}"
  },
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_2.1_python_yarn_cluster/bin/run.sh",
    "{connection_file}"
  ]
```
then referenced in the run.sh script as the initial arguments to the launcher (`launch_ipykernel.py` below) ...
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
1. Build a kernel specification file that identifies the process proxy class and connection file mode to be used.
2. Implement the process proxy class such that it supports the four primitive functions of `poll()`, `wait()`, `send_signal(signum)` and `kill()`.
3. Insert invocation of a launcher (if necessary) which builds the connection file - making it available to Elyra.

