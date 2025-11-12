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
