# Availability modes

Enterprise Gateway can be optionally configured in one of two "availability modes": _standalone_ or _replication_. When configured, Enterprise Gateway can recover from failures and reconnect to any active remote kernels that were previously managed by the terminated EG instance. As such, both modes require that kernel session persistence also be enabled via `KernelSessionManager.enable_persistence=True`.

```{note}
Kernel session persistence will be automtically enabled whenever availability mode is configured.
```

```{caution}
**Availability modes and kernel session persistence should be considered experimental!**

Known issues include:
1. Culling configurations do not account for different nodes and therefore could result in the incorrect culling of kernels.
2. Each "node switch" requires a manual reconnect to the kernel.

We hope to address these in future releaases (depending on demand).
```

## Standalone availability

_Standalone availability_ assumes that, upon failure of the original EG instance, another EG instance will be started. Upon startup of the second instance (following the termination of the first), EG will attempt to load and reconnect to all kernels that were deemed active when the previous instance terminated. This mode is somewhat analogous to the classic HA/DR mode of _active-passive_ and is typically used when node resources are at a premium or the number of replicas (in the Kubernetes sense) must remain at 1.

To enable Enterprise Gateway for 'standalone' availability, configure `EnterpiseGatewayApp.availability_mode=standalone` or set env `EG_AVAILABILITY_MODE=standalone`.

Here's an example for starting Enterprise Gateway with standalone availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --EnterpriseGatewayApp.availability_mode=standalone > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

## Replication availability

With _replication availability_, multiple EG instances (or replicas) are operating at the same time, and fronted with some kind of reverse proxy or load balancer. Because state still resides within each `KernelManager` instance executing within a given EG instance, we strongly suggest configuring some form of _client affinity_ (a.k.a, "sticky session") to avoid node switches wherever possible since each node switch requires manual reconnection of the front-end (today).

```{tip}
Configuring client affinity is **strongly recommended**, otherwise functionality that relies on state within the servicing node (e.g., culling) can be affected upon node switches, resulting in incorrect behavior.
```

In this mode, when one node goes down, the subsequent request will be routed to a different node that doesn't know about the kernel. Prior to returning a `404` (not found) status code, EG will check its persisted store to determine if the kernel was managed and, if so, attempt to "hydrate" a `KernelManager` instance associated with the remote kernel. (Of course, if the kernel was running local to the downed server, chances are it cannot be _revived_.) Upon successful "hydration" the request continues as if on the originating node. Because _client affinity_ is in place, subsequent requests should continue to be routed to the "servicing node".

To enable Enterprise Gateway for 'replication' availability, configure `EnterpiseGatewayApp.availability_mode=replication` or set env `EG_AVAILABILITY_MODE=replication`.

```{attention}
To preserve backwards compatibility, if only kernel session persistence is enabled via `KernelSessionManager.enable_persistence=True`, the availability mode will be automatically configured to 'replication' if `EnterpiseGatewayApp.availability_mode` is not configured.
```

Here's an example for starting Enterprise Gateway with replication availability:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --EnterpriseGatewayApp.availability_mode=replication > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

# Kernel Session Persistence

Enabling kernel session persistence allows Jupyter Notebooks to reconnect to kernels when Enterprise Gateway is restarted and forms the basis for the _availability modes_ described above. Enterprise Gateway provides two ways of persisting kernel sessions: _File Kernel Session Persistence_ and _Webhook Kernel Session Persistence_, although others can be provided by subclassing `KernelSessionManager` (see below).

```{attention}
Due to its experimental nature, kernel session persistence is disabled by default. To enable this functionality, you must configure `KernelSessionManger.enable_persistence=True` or configure `EnterpriseGatewayApp.availability_mode` to either `standalone` or `replication`.
```

As noted above, the availability modes rely on the persisted information relative to the kernel. This information consists of the arguments and options used to launch the kernel, along with its connection information. In essence, it consists of any information necessary to re-establish communication with the kernel.

## File Kernel Session Persistence

File Kernel Session Persistence stores kernel sessions as files in a specified directory. To enable this form of persistence, set the environment variable `EG_KERNEL_SESSION_PERSISTENCE=True` or configure `FileKernelSessionManager.enable_persistence=True`. To change the directory in which the kernel session file is being saved, either set the environment variable `EG_PERSISTENCE_ROOT` or configure `FileKernelSessionManager.persistence_root` to the directory. By default, the directory used to store a given kernel's session information is the `JUPYTER_DATA_DIR`.

```{note}
Because `FileKernelSessionManager` is the default class for kernel session persistence, configuring `EnterpriseGatewayApp.kernel_session_manager_class` to `enterprise_gateway.services.sessions.kernelsessionmanager.FileKernelSessionManager` is not necessary.
```

## Webhook Kernel Session Persistence

Webhook Kernel Session Persistence stores all kernel sessions to any database. In order for this to work, an API must be created. The API must include four endpoints:

- A `GET` that will retrieve a list of all kernel sessions from a database
- A `GET` that will take the kernel id as a path variable and retrieve that information from a database
- A `DELETE` that will delete all kernel sessions, where the body of the request is a list of kernel ids
- A `POST` that will take kernel id as a path variable and kernel session in the body of the request and save it to a database where the object being saved is:

```
    {
      kernel_id: UUID string,
      kernel_session: JSON
    }
```

To enable the webhook kernel session persistence, set the environment variable `EG_KERNEL_SESSION_PERSISTENCE=True` or configure `WebhookKernelSessionManager.enable_persistence=True`. To connect the API, set the environment variable `EG_WEBHOOK_URL` or configure `WebhookKernelSessionManager.webhook_url` to the API endpoint.

Because `WebhookKernelSessionManager` is not the default kernel session persistence class, an additional configuration step must be taken to instruct EG to use this class: `EnterpriseGatewayApp.kernel_session_manager_class = enterprise_gateway.services.sessions.kernelsessionmanager.WebhookKernelSessionManager`.

### Enabling Authentication

Enabling authentication is an option if the API requires it for requests. Set the environment variable `EG_AUTH_TYPE` or configure `WebhookKernelSessionManager.auth_type` to be either `Basic` or `Digest`. If it is set to an empty string authentication won't be enabled.

Then set the environment variables `EG_WEBHOOK_USERNAME` and `EG_WEBHOOK_PASSWORD` or configure `WebhookKernelSessionManager.webhook_username` and `WebhookKernelSessionManager.webhook_password` to provide the username and password for authentication.

## Bring Your Own Kernel Session Persistence

To introduce a different implementation, you must configure the kernel session manager class. Here's an example for starting Enterprise Gateway using a custom `KernelSessionManager` and 'standalone' availability. Note that setting `--MyCustomKernelSessionManager.enable_persistence=True` is not necessary because an availability mode is specified, but displayed here for completeness:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --EnterpriseGatewayApp.kernel_session_manager_class=custom.package.MyCustomKernelSessionManager \
   --MyCustomKernelSessionManager.enable_persistence=True \
   --EnterpriseGatewayApp.availability_mode=standalone > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

Alternative persistence implementations using SQL and NoSQL databases would be ideal and, as always, contributions are welcome!

## Testing Kernel Session Persistence

Once kernel session persistence has been enabled and configured, create a kernel by opening up a Jupyter Notebook. Save some variable in that notebook and shutdown Enterprise Gateway using `kill -9 PID`, where `PID` is the PID of gateway. Restart Enterprise Gateway and refresh you notebook tab. If all worked correctly, the variable should be loaded without the need to rerun the cell.

If you are using docker, ensure the container isn't tied to the PID of Enterprise Gateway. The container should still run after killing that PID.
