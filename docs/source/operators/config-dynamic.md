# Dynamic configurables

Enterprise Gateway also supports the ability to update configuration variables without having to
restart Enterprise Gateway. This enables the ability to do things like enable debug logging or
adjust the maximum number of kernels per user, all without having to restart Enterprise Gateway.

To enable dynamic configurables configure `EnterpriseGatewayApp.dynamic_config_interval` to a
positive value (default is 0 or disabled). Since this is the number of seconds to poll Enterprise Gateway's configuration files,
a value greater than 60 (1 minute) is recommended. This functionality works for most configuration
values, but does have the following caveats:

1. Any configuration variables set on the command line (CLI) or via environment variables are
   NOT eligible for dynamic updates. This is because Jupyter gives those values priority over
   file-based configuration variables.
1. Any configuration variables tied to background processing may not reflect their update if
   the variable is not _observed_ for changes. For example, the code behind
   `RemoteKernelManager.cull_idle_timeout` may not reflect changes to the timeout period if
   that variable is not monitored (i.e., observed) for changes.
1. Only `Configurables` registered by Enterprise Gateway are eligible for dynamic updates.
   Currently, that list consists of the following (and their subclasses): EnterpriseGatewayApp,
   RemoteKernelManager, KernelSpecManager, and KernelSessionManager.

As a result, operators and adminstrators are encouraged to configure Enterprise Gateway via configuration files with only static values configured via the command line or environment.

Note that if `EnterpriseGatewayApp.dynamic_config_interval` is configured with a positive value
via the configuration file (i.e., is eligible for updates) and is subsequently set to 0, then
dynamic configuration updates will be disabled until Enterprise Gateway is restarted with a
positive value. Therefore, we recommend `EnterpriseGatewayApp.dynamic_config_interval` be
configured via the command line or environment.
