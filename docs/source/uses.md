## Use Cases

Jupyter Enterprise Gateway makes possible the following uses cases:

* A company with many data analysts and a large Yarn cluster have found their Kernel Gateway server 
to be a bottleneck  due to the size of each kernel (spark driver) process.  By deploying Enterprise Gateway, 
their kernels can be launched as managed resources within Yarn, distributing the resource-intensive 
driver processes across the Yarn cluster.

* A company recently planed to deploy their Spark notebook services with Enterprise Gateway in a cluster where Mesos was 
the resource manager, besides the existing cluster managed by YARN they were already using from the open source side, 
so as to take advantages of some features that YARN didn't have. Since they were using Enterprise Gateway, 
they would need to implement the interface required by the resource manager components in Enterprise Gateway, 
so they could integrate Mesos plug-in with Enterprise Gateway similar to the way of YARN.

* ...
