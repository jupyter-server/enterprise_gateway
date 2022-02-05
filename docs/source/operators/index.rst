Documentation for Operators
===========================

These pages are targeted at *operators* using, configuring, and deploying Jupyter Enterprise Gateway.

**Use cases:**

- As an operator, I want to fix the bottleneck on the Jupyter Kernel Gateway server due to large number of kernels running on it and the size of each kernel (spark driver) process, by deploying the Enterprise Gateway, such that kernels can be launched as managed resources within YARN, distributing the resource-intensive driver processes across the YARN cluster, while still allowing the data analysts to leverage the compute power of a large YARN cluster.
- As an administrator, I want to constrain applications to specific port ranges so I can more easily identify issues and manage network configurations that adhere to my corporate policy.
- As an administrator, I want to constrain the number of active kernels that each of my users can have at any given time.

.. toctree::
   :caption: Operators
   :maxdepth: 2
   :name: operators

   getting-started
   getting-started-security
   getting-started-other-features
   Kernel Specifications
       kernel-local
       kernel-distributed
       kernel-yarn-cluster-mode
       kernel-yarn-client-mode
       kernel-spark-standalone
       kernel-kubernetes
       kernel-docker
       kernel-conductor
   config-options
   troubleshooting

