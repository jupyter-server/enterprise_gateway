# Launching Enterprise Gateway (common)

Very few arguments are necessary to minimally start Enterprise Gateway. The following command could be considered a minimal command:

```bash
jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0
```

where `--ip=0.0.0.0` exposes Enterprise Gateway on the public network and `--port_retries=0` ensures that a single instance will be started.

```{note}
The ability to target resource-managed clusters (and use remote kernels) will require additional configuration settings depending on the resource manager.  For additional information see the appropriate server-based deployment topic of our Operators Guide.
```

We recommend starting Enterprise Gateway as a background task. As a result, you might find it best to create a start script to maintain options, file redirection, etc.

The following script starts Enterprise Gateway with `DEBUG` tracing enabled (default is `INFO`) and idle kernel culling for any kernels idle for 12 hours with idle check intervals occurring every 60 seconds. The Enterprise Gateway log can then be monitored via `tail -F enterprise_gateway.log` and it can be stopped via `kill $(cat enterprise_gateway.pid)`

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG --RemoteKernelManager.cull_idle_timeout=43200 --MappingKernelManager.cull_interval=60 > $LOG 2>&1 &
if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```

```{tip}
Remember that any options set via the command-line will not be available for [dynamic configuration funtionality](config-dynamic.md#dynamic-configurables).
```
