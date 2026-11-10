# Configuring security

Jupyter Enterprise Gateway does not currently perform user _authentication_ but, instead, assumes that all users
issuing requests have been previously authenticated. Recommended applications for this are
[Apache Knox](https://knox.apache.org/) or [Jupyter Hub](https://jupyterhub.readthedocs.io/en/latest/)
(e.g., if gateway-enabled notebook servers were spawned targeting an Enterprise Gateway cluster).

This section introduces some security features inherent in Enterprise Gateway (with more to come).

## KERNEL_USERNAME

In order to convey the name of the authenticated user, `KERNEL_USERNAME` should be sent in the kernel creation request
via the `env:` entry. This will occur automatically within the gateway-enabled Notebook server since it propagates all environment variables
prefixed with `KERNEL_`. If the request does not include a `KERNEL_USERNAME` entry, one will be added to the kernel's
launch environment with the value of the gateway user.

This value is then used within the _authorization_ and _impersonation_ functionality.

## Authorization

By default, all users are authorized to start kernels. This behavior can be adjusted when situations arise where
more control is required. Basic authorization can be expressed in two ways.

### Authorized Users

The command-line or configuration file option: `EnterpriseGatewayApp.authorized_users` can be specified to contain a
list of user names indicating which users are permitted to launch kernels within the current gateway server.

On each kernel launched, the authorized users list is searched for the value of `KERNEL_USERNAME` (case-sensitive). If
the user is found in the list the kernel's launch sequence continues, otherwise HTTP Error 403 (Forbidden) is raised
and the request fails.

```{warning}
Since the `authorized_users` option must be exhaustive, it should be used only in situations where a small
and limited set of users are allowed access and empty otherwise.
```

### Unauthorized Users

The command-line or configuration file option: `EnterpriseGatewayApp.unauthorized_users` can be specified to contain a
list of user names indicating which users are **NOT** permitted to launch kernels within the current gateway server.
The `unauthorized_users` list is always checked prior to the `authorized_users` list. If the value of `KERNEL_USERNAME`
appears in the `unauthorized_users` list, the request is immediately failed with the same 403 (Forbidden) HTTP Error.

From a system security standpoint, privileged users (e.g., `root` and any users allowed `sudo` privileges) should be
added to this option.

### Authorization Failures

It should be noted that the corresponding messages logged when each of the above authorization failures occur are
slightly different. This allows the administrator to discern from which authorization list the failure was generated.

Failures stemming from _inclusion_ in the `unauthorized_users` list will include text similar to the following:

```
User 'bob' is not authorized to start kernel 'Spark - Python (YARN Client Mode)'. Ensure
KERNEL_USERNAME is set to an appropriate value and retry the request.
```

Failures stemming from _exclusion_ from a non-empty `authorized_users` list will include text similar to the following:

```
User 'bob' is not in the set of users authorized to start kernel 'Spark - Python (YARN Client Mode)'. Ensure
KERNEL_USERNAME is set to an appropriate value and retry the request.
```

## Client-selected kernel resources

Clients shape some resources of their kernels through `KERNEL_` variables in the kernel creation request (see
[Kernel Environment Variables](../users/kernel-envs.md)). Some of these choices decide what a kernel can reach beyond
its own container, so Enterprise Gateway checks them against limits the operator controls before it starts the kernel.
A request that goes beyond these limits fails with HTTP 400, and the error message names the setting that would
permit it. Values that the gateway passes on unchanged from its own environment (`EG_INHERITED_ENVS`) are not checked.
These checks also run on a kernel restart, before the running kernel is shut down, so tightening a limit while a kernel
is running causes a later restart to fail rather than leaving the kernel dead.

### Kubernetes volumes

`KERNEL_VOLUMES` and `KERNEL_VOLUME_MOUNTS` are added to the pod of Kubernetes kernels, and to the driver and executor
pods of Spark Operator kernels. Each volume in `KERNEL_VOLUMES` must have a valid name and exactly one volume type,
taken from the allowed list. By default, the allowed types are `emptyDir`, `persistentVolumeClaim`, `configMap` and
`secret`. Types are matched exactly, so `HostPath` does not match `hostPath`. Entries in `KERNEL_VOLUME_MOUNTS` may
only use the fields of a Kubernetes `VolumeMount` (`name`, `mountPath`, `readOnly`, `subPath`, `subPathExpr`,
`mountPropagation` and `recursiveReadOnly`).

```{versionchanged} 3.4.0
Earlier releases accepted any volume type. Clients that use other types, such as `hostPath`, `nfs` or `csi`, are now
rejected until the operator allows them.
```

To change the allowed types for every kernel, set `EG_ALLOWED_KERNEL_VOLUME_TYPES` (or
`--EnterpriseGatewayApp.allowed_kernel_volume_types`, or the Helm value `kernel.allowedVolumeTypes`) to a comma-separated list, or to `*` to allow any type. An empty
value allows none. To change them for one kernelspec, add an `allowed_volume_types` entry to its process proxy `config`
stanza. That entry replaces the gateway-wide list:

```json
"metadata": {
  "process_proxy": {
    "class_name": "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy",
    "config": {
      "image_name": "elyra/kernel-py:VERSION",
      "allowed_volume_types": "emptyDir,persistentVolumeClaim,nfs"
    }
  }
}
```

```{warning}
Types such as `hostPath`, `gitRepo` and `flexVolume` give a kernel access to the node it runs on. Only allow them
when everyone who can reach the gateway is trusted with that access. A `secret` volume can mount any Secret in the
kernel's namespace: with the default per-kernel namespaces that is limited to the kernel's own namespace, but with
`EG_SHARED_NAMESPACE=True` kernels run in the gateway's namespace, so remove `secret` from the list in that case.
```

### Container images

Clients can choose the image of a container-based kernel (Kubernetes, Spark Operator, Docker and Docker Swarm) with
`KERNEL_IMAGE`, and the image of Spark executors with `KERNEL_EXECUTOR_IMAGE`. These values must be well-formed image
references (`[registry/]repository[:tag][@digest]`, with a lowercase repository).

By default, any well-formed image is accepted. Kernels run client code by design, but an image chosen by the client
can also bring software the operator has not vetted, such as setuid binaries or programs that do not run a kernel at
all. To restrict images, set `EG_ALLOWED_KERNEL_IMAGES` (or `--EnterpriseGatewayApp.allowed_kernel_images`, or the Helm
value `kernel.allowedImages`) to a comma-separated list of repository patterns:

```bash
EG_ALLOWED_KERNEL_IMAGES="elyra/*,registry.example.com/data-science/*"
```

Patterns use shell-style wildcards (`*` and `?`) and match the image's repository, so tags and digests are not part of
the match. Repositories are compared the way Docker resolves them, with the registry and the path matched separately so
that a wildcard in the registry part cannot cross the `/` into the path: `elyra/*` matches `elyra/kernel-py:3.3.0` and
`docker.io/elyra/kernel-py` but not `elyra.example.com/kernel-py`; `python` matches the official `python` image;
`docker.io/*` matches any Docker Hub image; and a registry wildcard such as `*.dkr.ecr.us-west-2.amazonaws.com/*`
matches only hosts in that domain, not `evil.com/x.dkr.ecr.us-west-2.amazonaws.com/y`. A registry name includes any
port. The images configured for the kernel
(`image_name` and `executor_image_name` in its kernelspec, or `EG_KERNEL_IMAGE` and `EG_KERNEL_EXECUTOR_IMAGE`) are
always allowed. A kernelspec can replace the gateway-wide list with an `allowed_images` entry in its process proxy
`config` stanza.

### Kubernetes namespaces

By default, Enterprise Gateway creates a namespace for each Kubernetes or Spark Operator kernel and deletes it when the
kernel stops. Clients can instead name an existing namespace with `KERNEL_NAMESPACE` (and its service account with
`KERNEL_SERVICE_ACCOUNT_NAME`). Enterprise Gateway can create pods in any namespace, so the namespace a client names
decides which service accounts, secrets and volumes its kernel can use. A client-supplied namespace is therefore
accepted only if it matches `EG_ALLOWED_KERNEL_NAMESPACES` (or `--EnterpriseGatewayApp.allowed_kernel_namespaces`, or
the Helm value `kernel.allowedNamespaces`), a comma-separated list of namespace names or shell-style patterns:

```bash
EG_ALLOWED_KERNEL_NAMESPACES="team-*,data-science"
```

The list is empty by default, so every client-supplied namespace is rejected until the operator lists it. Kernels that
do not set `KERNEL_NAMESPACE` are not affected. A kernelspec can replace the gateway-wide list with an
`allowed_namespaces` entry in its process proxy `config` stanza.

Some namespaces are always rejected, even when the list is `*`:

- the namespace Enterprise Gateway runs in (`EG_NAMESPACE`), including when `EG_SHARED_NAMESPACE=True`. In that
  mode, kernels are placed in the gateway's namespace without the client naming it.
- `kube-*` namespaces, such as `kube-system`.
- namespaces that Enterprise Gateway created for another kernel that has not stopped yet. Enterprise Gateway confirms
  this against the Kubernetes API (the namespace carries a `kernel_id` label), so it holds across gateway replicas and
  restarts, not only within the process that created the namespace.

`KERNEL_SERVICE_ACCOUNT_NAME` must be a valid service account name, and a client may set a non-default account only
together with a client-supplied `KERNEL_NAMESPACE`. Without a namespace the kernel runs in a namespace Enterprise
Gateway chooses (a per-kernel namespace, or the gateway's own when `EG_SHARED_NAMESPACE=True`), where it falls back to
`EG_DEFAULT_KERNEL_SERVICE_ACCOUNT_NAME`; this stops a client from running the kernel as the gateway's own service
account. The service account itself is not checked, so only list namespaces whose service accounts every client may
use.

````{versionchanged} 3.4.0
Earlier releases accepted any `KERNEL_NAMESPACE`. Installations that pre-create kernel namespaces must now list them in
`EG_ALLOWED_KERNEL_NAMESPACES` before upgrading, or kernel creation requests that name them will fail with an error
like:

```text
KERNEL_NAMESPACE 'team-a' is not permitted. Enterprise Gateway only launches kernels into client-specified
namespaces that match EG_ALLOWED_KERNEL_NAMESPACES (or allowed_namespaces in the kernelspec's process-proxy
config). Ask your Enterprise Gateway operator to add it, or omit KERNEL_NAMESPACE so Enterprise Gateway creates
a namespace for the kernel.
```
````

```{note}
The allowed list decides which namespaces clients may use, not which client may use which namespace.
`KERNEL_USERNAME` is supplied by the client, so any client that can reach the gateway can name any listed namespace.
```

### Spark options

On Spark-on-Kubernetes kernels, the bundled kernelspecs append the client's `KERNEL_EXTRA_SPARK_OPTS` to their
`spark-submit` command after the options that place the driver pod (namespace, service account, container images, pod
labels). Because a later `--conf` wins, Enterprise Gateway rejects (HTTP 400) a `KERNEL_EXTRA_SPARK_OPTS` that sets any
of the options it manages itself: `spark.kubernetes.namespace`, `spark.kubernetes.authenticate.*`, the driver/executor
`container.image`, `podTemplateFile` and `secrets` keys, and the `--master`, `--deploy-mode` and `--proxy-user` flags.
Spark volume options (`spark.kubernetes.{driver,executor}.volumes.<type>.*`) are held to the same type allowlist as
[Kubernetes volumes](#kubernetes-volumes). Options such as driver and executor memory and cores remain available.

### Pod Security for kernel namespaces

The checks above cover what clients send to Enterprise Gateway. A kernel can also create pods itself: the
`kernel-controller` role lets it create pods in its namespace, which Spark drivers need for their executors. To keep
those pods off the node, Enterprise Gateway labels the namespaces it creates to enforce the Kubernetes `baseline`
[Pod Security Standard](https://kubernetes.io/docs/concepts/security/pod-security-standards/), which rejects host
paths, host namespaces and privileged containers. Set `EG_KERNEL_NAMESPACE_POD_SECURITY` (Helm value `kernel.namespacePodSecurity`) to
`privileged`, `baseline` or `restricted` to change the standard, or to an empty value to add no labels. Namespaces created outside Enterprise
Gateway, such as those listed in `EG_ALLOWED_KERNEL_NAMESPACES`, are not labeled by it, so label them yourself (see
[Kubernetes namespaces](deploy-kubernetes.md#namespaces)).

## User Impersonation

The Enterprise Gateway server leverages other technologies to implement user impersonation when launching kernels. This
option is configured via two pieces of information: `EG_IMPERSONATION_ENABLED` and
`KERNEL_USERNAME`.

`EG_IMPERSONATION_ENABLED` indicates the intention that user impersonation should be performed and can also be conveyed
via the command-line boolean option `EnterpriseGatewayApp.impersonation_enabled` (default = False).

`KERNEL_USERNAME` is also conveyed within the environment of the kernel launch sequence where
its value is used to indicate the user that should be impersonated.

### Impersonation in Hadoop YARN clusters

In a cluster managed by the Hadoop YARN resource manager, impersonation is implemented by leveraging kerberos, and thus require
this security option as a pre-requisite for user impersonation. When user impersonation is enabled, kernels are launched
with the `--proxy-user ${KERNEL_USERNAME}` which will tell YARN to launch the kernel in a container used by the provided
user name.

```{admonition} Important!
:class: warning
When using kerberos in a YARN managed cluster, the gateway user (`elyra` by default) needs to be set up as a
`proxyuser` superuser in hadoop configuration. Please refer to the
[Hadoop documentation](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-common/Superusers.html)
regarding the proper configuration steps.
```

### SPNEGO Authentication to YARN APIs

When kerberos is enabled in a YARN managed cluster, the administration uis can be configured to require authentication/authorization
via SPENEGO. When running Enterprise Gateway in a environment configured this way, we need to convey an extra configuration
to enable the proper authorization when communicating with YARN via the YARN APIs.

`YARN_ENDPOINT_SECURITY_ENABLED` indicates the requirement to use SPNEGO authentication/authorization when connecting with the
YARN APIs and can also be conveyed via the command-line boolean option `EnterpriseGatewayApp.yarn_endpoint_security_enabled`
(default = False)

### Impersonation in Standalone or YARN Client Mode

Impersonation performed in standalone or YARN cluster modes tends to take the form of using `sudo` to perform the
kernel launch as the target user. This can also be configured within the
[run.sh](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernelspecs/spark_python_yarn_client/bin/run.sh)
script and requires the following:

1. The gateway user (i.e., the user in which Enterprise Gateway is running) must be enabled to perform sudo operations
   on each potential host. This enablement must also be done to prevent password prompts since Enterprise Gateway runs
   in the background. Refer to your operating system documentation for details.
1. Each user identified by `KERNEL_USERNAME` must be associated with an actual operating system user on each host.
1. Once the gateway user is configured for `sudo` privileges it is **strongly recommended** that that user be included
   in the set of `unauthorized_users`. Otherwise, kernels not configured for impersonation, or those requests that do not
   include `KERNEL_USERNAME`, will run as the, now, highly privileged gateway user!

```{warning}
Should impersonation be disabled after granting the gateway user elevated privileges, it is
**strongly recommended** those privileges be revoked (on all hosts) prior to starting kernels since those kernels
will run as the gateway user **regardless of the value of KERNEL_USERNAME**.
```

## SSH Tunneling

Jupyter Enterprise Gateway is configured to perform SSH tunneling on the five ZeroMQ kernel sockets as well as the
communication socket created within the launcher and used to perform remote and cross-user signalling functionality. SSH
tunneling is NOT enabled by default. Tunneling can be enabled/disabled via the environment variable `EG_ENABLE_TUNNELING=False`.
Note, there is no command-line or configuration file support for this variable.

Note that SSH by default validates host keys before connecting to remote hosts and the connection will fail for invalid
or unknown hosts. Enterprise Gateway honors this requirement, and invalid or unknown hosts will cause tunneling to fail.
Please perform necessary steps to validate all hosts before enabling SSH tunneling, such as:

- SSH to each node cluster and accept the host key properly
- Configure SSH to disable `StrictHostKeyChecking`

## Using Generic Security Service (Kerberos)

Jupyter Enterprise Gateway has support for SSH connections using GSS (for example Kerberos), which enables its deployment
without the use of an ssh key. The `EG_REMOTE_GSS_SSH` environment variable can be used to control this behavior.

```{seealso}
The list of [additional supported environment variables](config-add-env.md#additional-environment-variables).
```

## Conductor HA endpoints

Conductor kernels fail over to the client-supplied `KERNEL_CONDUCTOR_HA_ENDPOINTS` hosts using credential-bearing
requests. Those hosts are restricted to the trust boundary configured by `EG_CONDUCTOR_HA_ALLOWED_HOSTS` (by
default, the DNS domain of `EG_CONDUCTOR_ENDPOINT`). See
[High-availability (HA) Conductor endpoints](deploy-conductor.md#high-availability-ha-conductor-endpoints).

The `Authorization` header carrying the JWT or EGO PlatformToken on these calls is replaced with the redaction
mask (`EG_REDACTION_MASK`, default `********`) wherever the Conductor process proxy logs the curl command, so these
credentials are not written to the logs.

## Securing Enterprise Gateway Server

### Using SSL for encrypted communication

Enterprise Gateway supports Secure Sockets Layer (SSL) communication with its clients. With SSL enabled, all the
communication between the server and client are encrypted and highly secure.

1. You can start Enterprise Gateway to communicate via a secure protocol mode by setting the `certfile` and `keyfile`
   options with the command:

   ```
   jupyter enterprisegateway --ip=0.0.0.0 --port_retries=0 --certfile=mycert.pem --keyfile=mykey.key
   ```

   As server starts up, the log should reflect the following,

   ```
   [EnterpriseGatewayApp] Jupyter Enterprise Gateway at https://localhost:8888
   ```

   Note: Enterprise Gateway server is started with `HTTPS` instead of `HTTP`, meaning server side SSL is enabled.

   ````{tip}
   A self-signed certificate can be generated with openssl. For example, the following command will create a
   certificate valid for 365 days with both the key and certificate data written to the same file:

   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout mykey.key -out mycert.pem
   ````

1. With Enterprise Gateway server SSL enabled, now you need to configure the client side SSL, which is accomplished via the Gateway configuration options embedded in Notebook server.

   During Jupyter Notebook server startup, export the following environment variables where the gateway-enabled server has access
   during runtime:

   ```bash
   export JUPYTER_GATEWAY_CLIENT_CERT=${PATH_TO_PEM_FILE}
   export JUPYTER_GATEWAY_CLIENT_KEY=${PATH_TO_KEY_FILE}
   export JUPYTER_GATEWAY_CA_CERTS=${PATH_TO_SELFSIGNED_CA}
   ```

   ```{note}
   If using a self-signed certificate, you can set `JUPYTER_GATEWAY_CA_CERTS` same as `JUPYTER_GATEWAY_CLIENT_CERT`.
   ```

### Using Enterprise Gateway configuration file

You can also utilize the [Enterprise Gateway configuration file](config-file.md#configuration-file-options) to set static configurations for the server.

To enable SSL from the configuration file, modify the corresponding parameter to the appropriate value.

```
c.EnterpriseGatewayApp.certfile = '/absolute/path/to/your/certificate/fullchain.pem'
c.EnterpriseGatewayApp.keyfile = '/absolute/path/to/your/certificate/privatekey.key'
```

Using configuration file achieves the same result as starting the server with `--certfile` and `--keyfile`, this way
provides better readability and maintainability.

After configuring the above, the communication between gateway-enabled Notebook Server and Enterprise Gateway is SSL enabled.
