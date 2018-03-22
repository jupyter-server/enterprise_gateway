## Security Features
Jupyter Enterprise Gateway does not currently perform user _authentication_ but, instead, assumes that all users
issuing requests have been previously authenticated.  Recommended applications for this are 
[Apache Knox](https://knox.apache.org/) or perhaps even [Jupyter Hub](https://jupyterhub.readthedocs.io/en/latest/) 
(e.g., if nb2kg-enabled notebook servers were spawned targeting an Enterprise Gateway cluster).

This section introduces some of the security features inherent in Enterprise Gateway (with more to come).

**KERNEL_USERNAME**

In order to convey the name of the authenicated user, `KERNEL_USERNAME` should be sent in the kernel creation request 
via the `env:` entry.  This will occur automatically within NB2KG since it propagates all environment variables 
prefixed with `KERNEL_`.  If the request does not include a `KERNEL_USERNAME` entry, one will be added to the kernel's
launch environment with the value of the gateway user.

This value is then used within the _authorization_ and _impersonation_ functionality.

### Authorization
By default, all users are authorized to start kernels.  This behavior can be adjusted when situations arise where
more control is required.  Basic authorization can be expressed in two ways.

##### Authorized Users
The command-line or configuration file option: `EnterpriseGatewayApp.authorized_users` can be specified to contain a
list of user names indicating which users are permitted to launch kernels within the current gateway server.  

On each kernel launched, the authorized users list is searched for the value of `KERNEL_USERNAME` (case-sensitive).  If 
the user is found in the list the kernel's launch sequence continues, otherwise HTTP Error 403 (Forbidden) is raised
and the request fails.

**Warning:** Since the `authorized_users` option must be exhaustive, it should be used only in situations where a small 
and limited set of users are allowed access and empty otherwise.
 
##### Unauthorized Users
The command-line or configuration file option: `EnterpriseGatewayApp.unauthorized_users` can be specified to contain a
list of user names indicating which users are **NOT** permitted to launch kernels within the current gateway server. 
The `unauthorized_users` list is always checked prior to the `authorized_users` list.  If the value of `KERNEL_USERNAME`
appears in the `unauthorized_users` list, the request is immediately failed with the same 403 (Forbidden) HTTP Error.

From a system security standpoint, privileged users (e.g., `root` and any users allowed `sudo` privileges) should be
added to this option.

##### Authorization Failures

It should be noted that the corresponding messages logged when each of the above authorization failures occur are 
slightly different.  This allows the administrator to discern from which authorization list the failure was generated.  

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

### User Impersonation

User impersonation is not performed with the Enterprise Gateway server, but is instead performed within the kernelspec
framework.  With respect to the Enterprise Gateway sample kernels, impersonation is triggered from within the `run.sh`
scripts.  However, the Enterprise Gateway server is what communicates the intention to perform user via two pieces of
information: `EG_IMPERSONATION_ENABLED` and `KERNEL_USERNAME`.

`EG_IMPERSONATION_ENABLED` indicates the intention that user impersonation should be performed and is conveyed via
the command-line boolean option `EnterpriseGatewayApp.impersonation_enabled` (default = False).  This value is then
set into the environment used to launch the kernel, where `run.sh` then acts on it - performing the appropriate logic
to trigger user impersonation when True.  As a result, it is important that the contents of kernelspecs also be secure
and trusted.

`KERNEL_USERNAME` is also conveyed within the environment of the kernel launch sequence where 
its value is used to indicate the user that should be impersonated.

##### Impersonation in YARN Cluster Mode
The recommended approach for performing user impersonation when the kernel is launched using the YARN resource manager
is to configure the `spark-submit` command within 
[run.sh](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kernelspecs/spark_python_yarn_cluster/bin/run.sh)
to use the `--proxy-user ${KERNEL_USERNAME}` option.  This YARN option  requires that kerberos be configured within the
cluster.  In addition the gateway user (`elyra` by default) needs to be set up as a `proxyuser` in hadoop configs.
Please refer to the
[Hadoop documentation](https://hadoop.apache.org/docs/current/hadoop-project-dist/hadoop-common/Superusers.html) 
regarding the proper configurations.

##### Impersonation in Standalone or YARN Client Mode
Impersonation performed in standalone or YARN cluster modes tends to take the form of using `sudo` to perform the 
kernel launch as the target user.  This can also be configured within the 
[run.sh](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kernelspecs/spark_python_yarn_client/bin/run.sh)
script and requires the following:

1. The gateway user (i.e., the user in which Enterprise Gateway is running) must be enabled to perform sudo operations
on each potential host.  This enablement must also be done to prevent password prompts since Enterprise Gateway runs
in the background.  Refer to your operating system documentation for details.
2. Each user identified by `KERNEL_USERNAME` must be associated with an actual operating system user on each host.
3. Once the gateway user is configured for `sudo` privileges it is **strongly recommended** that that user be included
in the set of `unauthorized_users`.  Otherwise, kernels not configured for impersonation, or those requests that do not
include `KERNEL_USERNAME`, will run as the, now, highly privileged gateway user!  

WARNING: Should impersonation be disabled after granting the gateway user elevated privileges, it is 
**strongly recommended** those privileges be revoked (on all hosts) prior to starting kernels since those kernels
will run as the gateway user **regardless of the value of KERNEL_USERNAME**.

### SSH Tunneling

Jupyter Enterprise Gateway is now configured to perform SSH tunneling on the five ZeroMQ kernel sockets as well as the 
communication socket created within the launcher and used to perform remote and cross-user signalling functionality.

Note that SSH tunneling is enabled by default. In order to troubleshoot related issues, tunneling can be disabled via
the environment variable `EG_ENABLE_TUNNELING=False`.  Note, there is no command-line or configuration file support
for this variable.

