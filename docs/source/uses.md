## Use Cases

Jupyter Enterprise Gateway addresses specific use cases for different personas.  We list a few below:

- **As an administrator**,  I want to fix the bottleneck on the Kernel Gateway server due to large number of kernels
running on it and the size of each kernel (spark driver) process, by deploying the Enterprise Gateway, such that
kernels can be launched as managed resources within Yarn, distributing the resource-intensive driver processes across
the Yarn cluster, while still allowing the data analysts to leverage the compute power of a large Yarn cluster.

- **As an administrator**, I want to have some user isolation such that user processes are protected against each
other and user can preserve and leverage their own environment, i.e. libraries and/or packages.

- **As a data scientist**, I want to run my notebook using the Enterprise Gateway such that I can free up resources
on my own laptop and leverage my company's large Yarn cluster to run my compute-intensive jobs.

- **As a solution architect**, I want to explore supporting a different resource manager with Enterprise Gateway,
i.e. Kubernetes, by extending and implementing a new ProcessProxy class, i.e. K8ProcessProxy, such that I can easily
take advantage of specific functionality provided by the resource manager.

