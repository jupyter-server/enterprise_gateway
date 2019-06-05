## Vanilla

This page describes the approach taken for integrating Enterprise Gateway into a vanilla set of hosts, without cluster resource managers.

Following kernelspec is available on Vanilla mode:

+ python_distributed

Install the `python_distributed` kernelspec on all nodes.

``` Bash
wget https://github.com/jupyter/enterprise_gateway/releases/download/v2.0.0rc1/jupyter_enterprise_gateway_kernelspecs-2.0.0rc1.tar.gz
KERNELS_FOLDER=/usr/local/share/jupyter/kernels
tar -zxvf jupyter_enterprise_gateway_kernelspecs-2.0.0.dev2.tar.gz --strip 1 --directory $KERNELS_FOLDER/python_distributed/ python_distributed/
```

The `python_distributed` kernelspec uses `DistributedProcessProxy` which is responsible for the launch and management of kernels distributed across and explicitly defined set of hosts using ssh. Hosts are determined via a round-robin algorithm (that we should make pluggable someday).

**QUESTIONS: how to set the list of hosts - Also, SSH should be available passwordless, right? Which user should be used?***
