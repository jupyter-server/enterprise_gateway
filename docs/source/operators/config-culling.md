# Culling idle kernels

With the adoption of notebooks and interactive development for data science, a new "resource utilization" pattern has arisen, where kernel resources are locked for a given notebook, but due to interactive development processes it might be idle for a long period of time causing the cluster resources to starve. One way to workaround this problem is to enable the culling of idle kernels after a specific timeout period.

Idle kernel culling is set to “off” by default. It’s enabled by setting `--RemoteKernelManager.cull_idle_timeout` to a positive value representing the number of seconds a kernel must remain idle to be culled (default: 0, recommended: 43200, 12 hours).

```{tip}
When managing large clusters with limited resources, we recommend enabling the culling of idle kernels.
```

You can also configure the interval that the kernels are checked for their idle timeouts by adjusting the setting `--RemoteKernelManager.cull_interval` to a positive value. If the interval is not set or set to a non-positive value, the system uses 300 seconds as the default value: (default: 300 seconds).

There are use-cases where we would like to enable only culling of idle kernels that have no connections (e.g. the notebook browser was closed without stopping the kernel first), this can be configured by adjusting the setting `--RemoteKernelManager.cull_connected` (default: False).

Here's an updated start script that provides some default configuration to enable the culling of idle kernels:

```bash
#!/bin/bash

LOG=/var/log/enterprise_gateway.log
PIDFILE=/var/run/enterprise_gateway.pid

jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --log-level=DEBUG \
   --RemoteKernelManager.cull_idle_timeout=43200 --MappingKernelManager.cull_interval=60 > $LOG 2>&1 &

if [ "$?" -eq 0 ]; then
  echo $! > $PIDFILE
else
  exit 1
fi
```
