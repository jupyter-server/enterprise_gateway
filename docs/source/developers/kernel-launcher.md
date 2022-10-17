# Implementing a kernel launcher

A new implementation for a [_kernel launcher_](../contributors/system-architecture.md#kernel-launchers) becomes necessary when you want to introduce another kind of kernel to an existing configuration. Out of the box, Enterprise Gateway provides [kernel launchers](https://github.com/jupyter-server/enterprise_gateway/tree/main/etc/kernel-launchers) that support the IPython kernel, the Apache Toree scala kernel, and the R kernel - IRKernel. There are other "language-agnostic kernel launchers" provided by Enterprise Gateway, but those are used in container environments to start the container or pod where the "kernel image" uses on the three _language-based_ launchers to start the kernel within the container.

Its generally recommended that the launcher be written in the language of the kernel, but that is not a requirement so long as the launcher can start and manage the kernel's lifecycle and issue interrupts (if the kernel does not support message-based interrupts itself).

To reiterate, the four tasks of a kernel launcher are:

1. Create the necessary connection information based on the 5 zero-mq ports, a signature key and algorithm specifier, along with a _gateway listener_ socket.
1. Conveyance of the connection (and listener socket) information back to the Enterprise Gateway process after encrypting the information using AES, then encrypting the AES key using the provided public key.
1. Invocation of the target kernel.
1. Listen for interrupt and shutdown requests from Enterprise Gateway on the communication socket and carry out the action when appropriate.

## Creating the connection information

If your target kernel exists, then there is probably support for creating ZeroMQ ports. If this proves difficult, you may be able to take a _hybrid approach_ where the connection information, encryption and listener portion of things is implemented in Python, while invocation takes place in the native language. This is how the [R kernel-launcher](https://github.com/jupyter-server/enterprise_gateway/tree/main/etc/kernel-launchers/R/scripts) support is implemented.

When creating the connection information, your kernel launcher should handle the possibility that the `--port-range` option has been specified such that each port should reside within the specified range.

The port used between Enterprise Gateway and the launcher, known as the _communication port_ should also adhere to the port range. It is not required that this port be ZeroMQ (and is not a ZMQ port in existing implementations).

## Encrypting the connection information

The next task of the kernel launcher is sending the connection information back to the Enterprise Gateway server. Prior to doing this, the connection information, including the communication port, are encrypted using AES encryption and a 16-byte key. The AES key is then encrypted using the public key specified in the `public_key` parameter. These two fields (the AES-encrypted payload and the publice-key-encrypted AES key) are then included into a JSON structure that also include the launcher's version information and base64 encoded. Here's such an example from the [Python kernel launcher](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/etc/kernel-launchers/python/scripts/launch_ipykernel.py#L188-L209).

The payload is then [sent back on a socket](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/etc/kernel-launchers/python/scripts/launch_ipykernel.py#L212-L256) identified by the `--response-address` option.

## Invoking the target kernel

For the R kernel launcher, the kernel is started using [`IRKernel::main()`](https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/etc/kernel-launchers/R/scripts/launch_IRkernel.R#L252) after the `SparkContext` is initialized based on the `spark-context-initialization-mode` parameter.

The scala kernel launcher works similarly in that the Apache Toree kernel provides an ["entrypoint" to start the kernel](https://github.com/jupyter-server/enterprise_gateway/blob/00d7376b932eacd347b3c32c863691bfbad53b86/etc/kernel-launchers/scala/toree-launcher/src/main/scala/launcher/ToreeLauncher.scala#L332), however, because the Toree kernel initializes a `SparkContext` itself, the need to do so is conveyed directly to the kernel.

For the Python kernel launcher, it creates a namespace instance that contains the `SparkContext` information, if requested to do so via the `spark-context-initialization-mode` parameter, instantiates an `IPKernelApp` instance using the configured namespace, then calls the [`start()`](https://github.com/ipython/ipykernel/blob/6f448d280dadbff7245f4b28b5e210c899d79342/ipykernel/kernelapp.py#L694) method.

### Invoking subclasses of `ipykernel.kernelbase.Kernel`

Because the python kernel launcher uses `IPKernelApp`, support for any subclass of `ipykernel.kernelbase.Kernel` can be launched by EG's Python kernel launcher.

To specify an alternate subclass, add `--kernel-class-name` (along with the specified dotted class string) to the `kernel.json` file's `argv` stanza. EG's Python launcher will import that class and pass it as a parameter to `IPKernelApp.initialize()`.

Here's an example `kernel.json` file that launches the "echo" kernel using the `DistributedProcessProxy`:

```JSON
{
  "display_name": "Echo",
  "language": "text",
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.distributed.DistributedProcessProxy"
    }
  },
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/echo/scripts/launch_ipykernel.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}",
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "none",
    "--kernel-class-name",
    "echo_kernel.kernel.EchoKernel"
  ]
}
```

```{admonition} Important!
The referenced `kernel-class-name` package must first be properly installed on all nodes where the associated process-proxy will run.
```

## Listening for interrupt and shutdown requests

The last task that must be performed by a kernel launcher is to listen on the communication port for work. There are currently two requests sent on the port, a signal event and a shutdown request.

The signal event is of the form `{"signum": n}` where the string `'signum'` indicates a signal event and `'n'` is an integer specifying the signal number to send to the kernel. Typically, the value of 'n' is `2` representing `SIGINT` and used to interrupt any current processing. As more kernels adopt a message-based interrupt approach, this will not be as common. Enterprise Gateway also uses this event to perform its `poll()` implementation by sending `{"signum": 0}`. Raising a signal of 0 to a process is common way to determine the process is still alive.

The event is a shutdown request. This is sent when the process proxy has typically terminated the kernel and it's just performing its final cleanup. The form of this request is `{"shutdown": 1}`. This is what instructs the launcher to abandon listening on the communication socket and to exit.

## Other parameters

Besides `--port-range`, `--public-key`, and `--response-address`, the kernel launcher needs to support `--kernel-id` that indicates the kernel's ID as known to the Gateway server. It should also tolerate the existence of `--spark-context-initialization-mode` but, unless applicable for Spark enviornments, should only support values of `"none"` for this option.
