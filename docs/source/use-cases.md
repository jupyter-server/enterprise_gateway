## Use Cases

Jupyter Enterprise Gateway addresses specific use cases for different personas.  We list a few below:

- **As an administrator**,  I want to fix the bottleneck on the Jupyter Kernel Gateway server due to large number of kernels
running on it and the size of each kernel (spark driver) process, by deploying the Enterprise Gateway, such that
kernels can be launched as managed resources within YARN, distributing the resource-intensive driver processes across
the YARN cluster, while still allowing the data analysts to leverage the compute power of a large YARN cluster.

- **As an administrator**, I want to have some user isolation such that user processes are protected against each
other and user can preserve and leverage their own environment, i.e. libraries and/or packages.

- **As a data scientist**, I want to run my notebook using the Enterprise Gateway such that I can free up resources
on my own laptop and leverage my company's large YARN cluster to run my compute-intensive jobs.

- **As a solution architect**, I want to explore supporting a different resource manager with Enterprise Gateway,
e.g. Kubernetes, by extending and implementing a new ProcessProxy class such that I can easily
take advantage of specific functionality provided by the resource manager.

- **As an administrator**, I want to constrain applications to specific port ranges so I can more easily identify
issues and manage network configurations that adhere to my corporate policy.

- **As an administrator**, I want to constrain the number of active kernels that each of my users can have at any 
given time.

- **As a solution architect**, I want to easily integrate the ability to launch remote kernels with existing platforms, 
so I can leverage my compute cluster in a customizable way.
