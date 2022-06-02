# Availability modes

Enterprise Gateway can be optionally configured in one of two "availability modes": _single-instance_ or _multi-instance_. When configured, Enterprise Gateway can recover from failures and reconnect to any active remote kernels that were previously managed by the terminated EG instance. As such, both modes require that kernel session persistence also be enabled via `KernelSessionManager.enable_persistence=True`.

```{caution}
**Availability modes and kernel session persistence should be considered experimental!**

Known issues include:
1. Culling configurations do not account for different nodes and therefore could result in the incorrect culling of kernels.
2. Each "node switch" requires a manual reconnect to the kernel.

We hope to address these in future releaases (depending on demand).
```

## Single-instance availability

_Single-instance availability_ assumes that, upon failure of the original EG instance, another EG instance will be started. Upon startup of the second instance (following the termination of the first), EG will attempt to load and reconnect to all kernels that were deemed active when the previous instance terminated. This mode is somewhat analogous to the classic HA/DR mode of _active-passive_ and is typically used when node resources are at a premium or the number of replicas (in the Kubernetes sense) must remain at 1.

To configure Enterprise Gateway for 'single-instance' availability, you must first enable session persistence as noted above and configure `EnterpiseGatewayApp.availability_mode=single-instance` or set env `EG_AVAILABILITY_MODE=single-instance`.

Here's an example for starting Enterprise Gateway with single-instance availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --KernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=single-instance > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

## Multi-instance availability

With _multi-instance availability_, multiple EG instances are operating at the same time, and fronted with some kind of reverse proxy or load balancer. Because state still resides within each `KernelManager` instance executing within a given EG instance, we strongly suggest configuring some form of _client affinity_ (a.k.a, "sticky session") to avoid node switches wherever possible since each node switch requires manual reconnection of the front-end (today).

```{tip}
Configuring client affinity is **strongly recommended**, otherwise functionality that relies on state within the servicing node (e.g., culling) can be affected upon node switches, resulting in incorrect behavior.
```

In this mode, when one node goes down, the subsequent request will be routed to a different node that doesn't know about the kernel. Prior to returning a `404` (not found) status code, EG will check its persisted store to determine if the kernel was managed and, if so, attempt to "hydrate" a `KernelManager` instance associated with the remote kernel. (Of course, if the kernel was running local to the downed server, chances are it cannot be _revived_.) Upon successful "hydration" the request continues as if on the originating node. Because _client affinity_ is in place, subsequent requests should continue to be routed to the "servicing node".

To configure Enterprise Gateway for 'multi-instance' availability, you must first enable session persistence as noted above and configure `EnterpiseGatewayApp.availability_mode=multi-instance` or set env `EG_AVAILABILITY_MODE=multi-instance`.

```{attention}
To preserve backwards compatibility, if only kernel session persistence is enabled via `KernelSessionManager.enable_persistence=True`, the availability mode will be automatically configured to 'multi-instance' if `EnterpiseGatewayApp.availability_mode` is not configured.
```

Here's an example for starting Enterprise Gateway with multi-instance availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --KernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=multi-instance > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

## Kernel Session Persistence

```{attention}
Due to its experimental nature, kernel session persistence is disabled by default. To enable this functionality, you must configure `KernelSessionManger.enable_persistence=True`.
```

As noted above, the availability modes rely on the persisted information relative to the kernel. This information consists of the arguments and options used to launch the kernel, along with its connection information. In essence, it consists of any information necessary to re-establish communication with the kernel.

Kernel session persistence is unique to Enterprise Gateway and consists of a _bring-your-own_ model whereby subclasses of `KernelSessionManager` can be configured that manage their own persistent storage of kernel sessions. By default, Enterprise Gateway provides a `FileKernelSessionManager` that reads and writes kernel session information to a pre-configured directory. For use with `availability_mode` it is presumed that directory resides in a location accessible by all applicable nodes running Enterprise Gateway.

```{note}
This option can be also be set on subclasses of `KernelSessionsManager` (e.g., `FileKernelSessionManager.enable_persistence=True`).
```

By default, the directory used to store a given kernel's session information is the `JUPYTER_DATA_DIR`. This location can be configured using `FileKernelSessionManager.persistence_root` with a value of a fully-qualified path to an existing directory.

To introduce a different implementation, you must configure the kernel session manager class. Here's an example for starting Enterprise Gateway using a custom `KernelSessionManager` and 'single-instance' availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --EnterpriseGatewayApp.kernel_session_manager_class=custom.package.MyCustomKernelSessionManager \
   --MyCustomKernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=single-instance > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

Alternative persistence implementations using SQL and NoSQL databases would be ideal and, as always, contributions are welcome!
