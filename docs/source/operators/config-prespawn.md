# Kernel Prespawning

Enterprise Gateway can start a number of kernels as soon as it starts, so that warm kernels are already running when clients need them. This page describes what prespawning does, what it doesn't do, and how it interacts with other settings.

```{important}
Prespawned kernels are **not** handed out to new kernel requests. A request to start a kernel (`POST /api/kernels`) always starts a new kernel, even when prespawned kernels are idle. To use a prespawned kernel, a client must find it by listing kernels and connect to it by its kernel id.
```

## What prespawning does

When `prespawn_count` is set, Enterprise Gateway:

1. Starts that many kernels in the background once its IO loop is running. Startup does not wait for them.
1. Uses the same kernel specification for every prespawned kernel (see [Choosing the kernel](#choosing-the-kernel)).
1. Retries a kernel that fails to start up to two more times, after 1 second and then 2 seconds. Failures are logged, and Enterprise Gateway keeps running even if no kernel could be prespawned.
1. Launches each kernel under the user name `prespawn` (`KERNEL_USERNAME=prespawn`), with an environment that contains only the variables listed in `inherited_envs` (`EG_INHERITED_ENVS`). This is the same environment a kernel request that supplies an `env` gets.
1. Shuts the kernels down, along with every other kernel, when Enterprise Gateway stops.

Prespawning happens once, at startup. Changing `prespawn_count` afterwards has no effect until Enterprise Gateway is restarted.

## What prespawning doesn't do

- **No hand-off.** Kernel requests never receive a prespawned kernel.
- **No discovery by default.** Prespawned kernels can only be found by listing kernels, which is disabled by default. Enable it with `EG_LIST_KERNELS=True`; otherwise `GET /api/kernels` returns `403 Forbidden`.
- **No marking.** The kernels API doesn't say which kernels were prespawned. They appear as ordinary kernels.
- **No replenishment.** When a prespawned kernel is culled, dies, or is shut down, it isn't replaced.
- **No session persistence.** Prespawned kernels have no kernel session, so [session persistence and high availability](config-availability.md) don't cover them.
- **No per-user settings.** Prespawned kernels start before any user asks for them, so they can't carry a user's `KERNEL_` values, such as `KERNEL_NAMESPACE`, `KERNEL_IMAGE`, `KERNEL_UID`, `KERNEL_GID`, or volume mounts.

## Configuration

| Setting                                    | Environment variable     | Purpose                                                                                             |
| ------------------------------------------ | ------------------------ | --------------------------------------------------------------------------------------------------- |
| `EnterpriseGatewayApp.prespawn_count`      | `EG_PRESPAWN_COUNT`      | Number of kernels to prespawn. Default: `None` (no prespawning).                                    |
| `EnterpriseGatewayApp.default_kernel_name` | `EG_DEFAULT_KERNEL_NAME` | Kernel specification used for prespawned kernels.                                                   |
| `EnterpriseGatewayApp.list_kernels`        | `EG_LIST_KERNELS`        | Allows clients to list kernels, which is the only way to find prespawned kernels. Default: `False`. |

For example, to prespawn three kernels and let clients find them:

```bash
export EG_PRESPAWN_COUNT=3
export EG_LIST_KERNELS=True
jupyter enterprisegateway
```

The same settings on the command line:

```bash
jupyter enterprisegateway --EnterpriseGatewayApp.prespawn_count=3 --EnterpriseGatewayApp.list_kernels=True
```

Or in `jupyter_enterprise_gateway_config.py`:

```python
c.EnterpriseGatewayApp.prespawn_count = 3
c.EnterpriseGatewayApp.list_kernels = True
```

### Choosing the kernel

Prespawned kernels use `default_kernel_name` when it's set, and the kernel manager's default (`python3`) otherwise. Only one kernel specification can be prespawned.

```python
c.EnterpriseGatewayApp.default_kernel_name = "spark_python_kubernetes"
```

## Interaction with other settings

- **`max_kernels`**: if `prespawn_count` is greater than `max_kernels` (`EG_MAX_KERNELS`), Enterprise Gateway fails to start. Prespawned kernels also count toward `max_kernels`, so they reduce the number of kernels clients can start. With `max_kernels=10` and `prespawn_count=3`, clients can start 7.
- **`max_kernels_per_user`**: prespawned kernels don't count against any user's limit.
- **`authorized_users` and `unauthorized_users`**: these are checked against the user name `prespawn`. If you set `authorized_users` (`EG_AUTHORIZED_USERS`), include `prespawn`, or every prespawn attempt is refused. Adding `prespawn` to `unauthorized_users` (`EG_UNAUTHORIZED_USERS`) disables prespawning.
- **Impersonation**: with `EG_IMPERSONATION_ENABLED=True`, kernels that support impersonation run as the user `prespawn`, which must be a valid user wherever those kernels run.
- **Culling**: when `--RemoteKernelManager.cull_idle_timeout` is set, idle prespawned kernels are culled like any other kernel, and they aren't replaced. See [Culling idle kernels](config-culling.md).
- **Kubernetes**: with the default pod naming, prespawned kernel pods are named `prespawn-<kernel_id>`.

## Monitoring

Enterprise Gateway logs prespawning progress at the `INFO` level unless noted:

- `Prespawning <n> kernels...` when prespawning begins.
- `Prespawned kernel <kernel_id> created successfully` for each kernel that starts.
- `Attempt <n> to spawn kernel <index> failed: <error>. Retrying...` (`WARNING`) before each retry.
- `Failed to spawn kernel <index> after 3 attempts: <error>` (`ERROR`) when a kernel's last attempt fails.
- `Failed to prespawn kernel <index>: <error>` (`ERROR`) for each kernel that couldn't be started, once all attempts have finished.
- `Prespawn completed: <n> successful, <n> failed` when all attempts have finished.
- `Error during kernel prespawning: Failed to prespawn any kernels` (`ERROR`) when no kernel could be started, followed by Tornado's `Exception in callback` error with a traceback.

If `prespawn_count` is greater than `max_kernels`, Enterprise Gateway logs `The number of kernels to prespawn <n> is greater than the maximum number of kernels allowed <max>.` (`WARNING`) and fails to start.

With kernel listing enabled, list the running kernels, including prespawned ones:

```bash
curl http://localhost:8888/api/kernels
```

If an auth token is configured, add `-H "Authorization: token <token>"`.

## Migrating from Jupyter Kernel Gateway

Enterprise Gateway reads `KG_PRESPAWN_COUNT`, `KG_DEFAULT_KERNEL_NAME`, `KG_LIST_KERNELS`, and `KG_MAX_KERNELS` when the corresponding `EG_` variables aren't set. Prespawning behaves like Kernel Gateway's default `jupyter-websocket` mode: kernels start at startup, and clients find them by listing kernels.

Enterprise Gateway doesn't support the following Kernel Gateway settings related to prespawning. It doesn't read them, so setting them has no effect:

| Kernel Gateway setting                                         | What it does in Kernel Gateway                                                                           | In Enterprise Gateway                                     |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `KernelGatewayApp.force_kernel_name` (`KG_FORCE_KERNEL_NAME`)  | Overrides the kernel name in every kernel request.                                                       | Not supported. Each request starts the kernel it names.   |
| `KernelGatewayApp.api=kernel_gateway.notebook_http` (`KG_API`) | Serves a notebook's annotated cells as HTTP endpoints, spreading requests across the prespawned kernels. | Not supported. Use Kernel Gateway for notebook-http mode. |
