# Per-kernel overrides

As mentioned in the overview of [Process Proxy Configuration](../contributors/system-architecture.md#process-proxy-configuration)
capabilities, it's possible to override or amend specific system-level configuration values on a per-kernel basis. These capabilities can be implemented with the kernel specification's process-proxy `config` stanza or via environment variables.

## Per-kernel configuration overrides

The following enumerates the set of per-kernel configuration overrides:

- `remote_hosts`: This process proxy configuration entry can be used to override `--EnterpriseGatewayApp.remote_hosts`.
  Any values specified in the config dictionary override the globally defined values. These apply to all
  `DistributedProcessProxy` kernels.
- `yarn_endpoint`: This process proxy configuration entry can be used to override `--EnterpriseGatewayApp.yarn_endpoint`.
  Any values specified in the config dictionary override the globally defined values. These apply to all
  `YarnClusterProcessProxy` kernels. Note that you'll likely be required to specify a different `HADOOP_CONF_DIR`
  setting in the kernel.json's `env` stanza in order of the `spark-submit` command to target the appropriate YARN cluster.
- `authorized_users`: This process proxy configuration entry can be used to override
  `--EnterpriseGatewayApp.authorized_users`. Any values specified in the config dictionary override the globally
  defined values. These values apply to **all** process-proxy kernels, including the default `LocalProcessProxy`. Note
  that the typical use-case for this value is to not set `--EnterpriseGatewayApp.authorized_users` at the global level,
  but then restrict access at the kernel level.
- `unauthorized_users`: This process proxy configuration entry can be used to **_amend_**
  `--EnterpriseGatewayApp.unauthorized_users`. Any values specified in the config dictionary are **added** to the
  globally defined values. As a result, once a user is denied access at the global level, they will _always be denied
  access at the kernel level_. These values apply to **all** process-proxy kernels, including the default
  `LocalProcessProxy`.
- `port_range`: This process proxy configuration entry can be used to override `--EnterpriseGatewayApp.port_range`.
  Any values specified in the config dictionary override the globally defined values. These apply to all
  `RemoteProcessProxy` kernels.
- `conductor_ha_allowed_hosts`: This process proxy configuration entry can be used to override
  `--EnterpriseGatewayApp.conductor_ha_allowed_hosts`. Any values specified in the config dictionary override the
  globally defined values. These apply to all `ConductorClusterProcessProxy` kernels. See
  [High-availability (HA) Conductor endpoints](deploy-conductor.md#high-availability-ha-conductor-endpoints).
- `allowed_volume_types`: This process proxy configuration entry can be used to override
  `--EnterpriseGatewayApp.allowed_kernel_volume_types` with a comma-separated list of volume types. Any values
  specified in the config dictionary override the globally defined values. These apply to all
  `KubernetesProcessProxy` kernels, including Spark Operator kernels. See
  [Kubernetes volumes](config-security.md#kubernetes-volumes).
- `allowed_images`: This process proxy configuration entry can be used to override
  `--EnterpriseGatewayApp.allowed_kernel_images` with a comma-separated list of repository patterns. Any values
  specified in the config dictionary override the globally defined values. These apply to all container-based
  kernels (Kubernetes, Spark Operator, Docker and Docker Swarm). See
  [Container images](config-security.md#container-images).
- `allowed_namespaces`: This process proxy configuration entry can be used to override
  `--EnterpriseGatewayApp.allowed_kernel_namespaces` with a comma-separated list of namespace patterns. Any values
  specified in the config dictionary override the globally defined values. These apply to all
  `KubernetesProcessProxy` kernels, including Spark Operator kernels. See
  [Kubernetes namespaces](config-security.md#kubernetes-namespaces).

For the `allowed_volume_types`, `allowed_images` and `allowed_namespaces` overrides above, a `null` value means
"inherit the gateway-wide setting" rather than "no restriction". To widen or narrow a kernel, give the override an
explicit value (an empty string removes all entries).

## Per-kernel environment overrides

In some cases, it is useful to allow specific values that exist in a kernel.json `env` stanza to be
overridden on a per-kernel basis. For example, if the kernel.json supports resource limitations you
may want to allow some requests to have access to more memory or GPUs than another. Enterprise
Gateway enables this capability by honoring environment variables provided in the json request over
those same-named variables in the kernel.json `env` stanza.

Environment variables for which this can occur are any variables prefixed with `KERNEL_`
as well as any variables
listed in the `EnterpriseGatewayApp.client_envs` configurable trait (or via
the `EG_CLIENT_ENVS` variable). Likewise, environment variables of the Enterprise Gateway
server process listed in the `EnterpriseGatewayApp.inherited_envs` configurable trait
(or via the `EG_INHERITED_ENVS` variable)
are also available for replacement in the kernel process' environment.

See [Kernel Environment Variables](../users/kernel-envs.md) in the Users documentation section for a complete set of recognized `KERNEL_` variables.
