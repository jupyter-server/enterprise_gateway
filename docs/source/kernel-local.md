## Local Mode

The Local deployment can be useful for local development and is not meant to be run in production environments as it subjects the gateway server to resource exhaustion.

If you just want to try EG in a local setup, you can use the following kernelspec (no need for a launcher):

```json
{
  "display_name": "Python 3 Local",
  "language": "python", 
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.processproxy.LocalProcessProxy"
    }
  },
  "argv": [
    "python",
    "-m",
    "ipykernel_launcher",
    "-f",
    "{connection_file}"
  ]
}
```

`process_proxy` is optional (if Enterprise Gateway encounters a kernelspec without the `process_proxy` stanza, it will treat that kernelspec as if it contained `LocalProcessProxy`).

Side note: You can run a Local kernel in [Distributed mode](./kernel-distributed.md) by setting `remote_hosts` to the localhost. Why would you do that?

1. One reason is that it decreases the window in which a port conflict can occur since the 5 kernel ports are created by the launcher (within the same process and therefore closer to the actual invocation of the kernel) rather than by the server prior to the launch of the kernel process.
2. The second reason is that auto-restarted kernels - when an issue occurs - say due to a port conflict - will create a new set of ports rather than try to re-use the same set that produced the failure in the first place. In this case, you'd want to use the [per-kernel configuration](./config-options.html#per-kernel-configuration-overrides) approach and set `remote_hosts` in the config stanza of the `process_proxy` stanza (using the stanza instead of the global `EG_REMOTE_HOSTS` allows you to not interfere with the other resource managers configuration, e.g. Spark Standalone or YARN Client kernels - Those other kernels need to be able to continue leveraging the full cluster nodes).
