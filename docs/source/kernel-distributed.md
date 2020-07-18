## Distributed Mode

This page describes the approach taken for integrating Enterprise Gateway into a distributed set of hosts, without cluster resource managers.

The following sample kernelspecs are currently available on Distributed mode:

+ python_distributed

Install the `python_distributed` kernelspec on all nodes.

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz
KERNELS_FOLDER=/usr/local/share/jupyter/kernels
tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.2.0rc2.tar.gz --strip 1 --directory $KERNELS_FOLDER/python_distributed/ python_distributed/
```

The `python_distributed` kernelspec uses `DistributedProcessProxy` which is responsible for the launch and management of kernels distributed across and explicitly defined set of hosts using ssh. Hosts are determined via a round-robin algorithm (that we should make pluggable someday).

The set of remote hosts are derived from two places.

+ The configuration option: EnterpriseGatewayApp.remote_hosts who's default value comes from the env variable EG_REMOTE_HOSTS - which, itself, defaults to 'localhost'.
+ The config option can be overridden on a per-kernel basis if the process_proxy stanza contains a config stanza where there's a remote_hosts entry. If present, this value will be used instead.

You have to ensure passwordless SSH from the EG host to all other hosts for the user under which EG is run.
