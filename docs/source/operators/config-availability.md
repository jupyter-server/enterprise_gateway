# Availability modes

Enterprise Gateway can be optionally configured in one of two "availability modes": _active-active_ and _active-passive_. Both modes require that kernel session persistence also be enabled via `KernelSessionManager.enable_persistence=True`.

```{warning}
**Availability modes and kernel session persistence should be considered experimental!**
Known issues include:
1. Culling configurations do not account for different nodes and therefore could result in the premature culling of kernels.
2. Each "node switch" requires a manual reconnect to the kernel.

We hope to address these in future releaases (depending on demand).
```

## Active-active availability

To configure Enterprise Gateway for 'active-active' availability, you must first enable session persistence as noted above and configure `EnterpiseGatewayApp.availability_mode=active-active` or set env `EG_AVAILABILITY_MODE=active-active`.

```{note}
To preserve backwards compatibility, if only kernel session persistence is enabled via `KernelSessionManager.enable_persistence=True`, the availability mode will be automatically configured to 'active-active' if `EnterpiseGatewayApp.availability_mode` is not configured.
```

When configured, you should be able to run multiple instances of Enterprise Gateway, preferrably fronted with some kind of reverse proxy or load balancer. We also suggest configuring some form of _client affinity_ to avoid node switches wherever possible since each node switch requires manual reconnection of the front-end (today).

If one node goes down, the subsequent request originally destined for the downed node will be re-routed to another active node. That node's kernel handler will not recognize the kernel's ID, but, prior to returning 404 (NotFound), will attempt to locate the kernel in the persistent store and "hydrate" a `KernelManager` for the kernel that should still be running remotely. (Of course, if the kernel was running local to the downed server, chances are it cannot be _revived_.) Upon successful "hydration" the request continues on as if on the originating node. Because _client affinity_ is in place, subsequent requests should continue to be routed to the "servicing node".

Here's an example for starting Enterprise Gateway with active-active availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --KernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=active-active > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

## Active-passive availability

To configure Enterprise Gateway for 'active-passive' availability, you must first enable session persistence as noted above and configure `EnterpiseGatewayApp.availability_mode=active-passive` or set env `EG_AVAILABILITY_MODE=active-passive`.

Enterprise Gateway does not honor _active-passive_ availability in the classic sense in that there's a _hot stand-by_ node waiting to take over. Instead, the "stand-by" node needs to have Enterprise Gateway started **after** the primary node has gone down. That is, with _active-passive_ availability only one node has Enterprise Gateway running at a given time. As a result, this mode should be viewed more in terms of _disaster recovery_ than _high availability_. When started, the previously "passive node" loads the persisted sessions, attempting to associate each with a `KernelManager` instance.

As with _active-active_, the same culling and connectivity issues are present although because the node switching is not as frequent, the (current) annoyances are subdued.

Here's an example for starting Enterprise Gateway with active-passive availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --KernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=active-passive > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

## Kernel Session Persistence

As noted above, the availability modes rely on the persisted information relative to the kernel. This information consists of the arguments and options used to launch the kernel, along with its connection information. In essence, it consists of any information necessary to re-establish communication with the kernel.

Kernel session persistence is unique to Enterprise Gateway and consists of a _bring-your-own_ model whereby subclasses of `KernelSessionManager` can be configured that manage their own persistent storage of kernel sessions. By default, Enterprise Gateway provides a `FileKernelSessionManager` that reads and writes kernel session information to a pre-configured directory. For use with `availability_mode` it is presumed that directory resides in a location accessible by all applicable nodes running Enterprise Gateway.

We plan to include implementations using SQL and NoSQL databases as well and, as always, contributions are welcome.

Due to its experimental nature, kernel session persistence is disabled by default. To enable this functionality, you must configure `KernelSessionManger.enable_persistence=True`.

```{note}
This option can be also be set on subclasses of `KernelSessionsManager` (e.g., `FileKernelSessionManager.enable_persistence=True`).
```

By default, the directory used to store a given kernel's session information is the `JUPYTER_DATA_DIR`. This location can be configured using `FileKernelSessionManager.persistence_root` with a value of a fully-qualified path to an existing directory.

To introduce a different implementation, you must configure the kernel session manager class. Here's an example for starting Enterprise Gateway using a custom `KernelSessionManager` and 'active-passive' availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --EnterpriseGatewayApp.kernel_session_manager_class=custom.package.MyCustomKernelSessionManager \
   --MyCustomKernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=active-passive > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```
