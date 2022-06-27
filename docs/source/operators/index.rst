Operators Guide
===============

These pages are targeted at *operators* that need to deploy and configure a Jupyter Enterprise Gateway instance.

.. admonition:: Use cases

    - *As an operator, I want to fix the bottleneck on the Jupyter Kernel Gateway server due to large number of kernels running on it and the size of each kernel (spark driver) process, by deploying the Enterprise Gateway, such that kernels can be launched as managed resources within a Hadoop YARN cluster, distributing the resource-intensive driver processes across the cluster, while still allowing the multiple data analysts to leverage the compute power of a large cluster.*
    - *As an operator, I want to constrain applications to specific port ranges so I can more easily identify issues and manage network configurations that adhere to my corporate policy.*
    - *As an operator, I want to constrain the number of active kernels that each of my users can have at any given time.*


Deploying Enterprise Gateway
----------------------------
The deployment of Enterprise Gateway consists of several items, depending on
the nature of the target environment.  Because this topic differs depending on
whether the runtime environment is targeting containers or traditional servers,
we've separated the discussions accordingly.

Container-based deployments
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Enterprise Gateway includes support for two forms of container-based environments, Kubernetes and Docker.

.. toctree::
   :maxdepth: 1
   :name: container-deployments

   deploy-kubernetes
   deploy-docker

Server-based deployments
~~~~~~~~~~~~~~~~~~~~~~~~
Tasks for traditional server deployments are nearly identical with respect to
Enterprise Gateway's installation and invocation, differing slightly with how
the kernel specifications are configured.  As a result, we marked those topics
as "common" relative to the others.

.. toctree::
   :maxdepth: 1
   :name: node-deployments

   installing-eg
   installing-kernels
   launching-eg
   deploy-yarn-cluster
   deploy-conductor
   deploy-distributed
   deploy-single

Configuring Enterprise Gateway
------------------------------
Jupyter Enterprise Gateway adheres to
`Jupyter's common configuration approach <https://jupyter.readthedocs.io/en/latest/use/config.html>`_
. You can configure an instance of Enterprise Gateway using a configuration file (recommended), via command-line parameters, or by setting the corresponding environment variables.

.. toctree::
   :maxdepth: 1
   :name: configuring

   config-file
   config-cli
   config-add-env
   config-env-debug
   config-sys-env
   config-kernel-override
   config-dynamic
   config-culling
   config-availability
   config-security
