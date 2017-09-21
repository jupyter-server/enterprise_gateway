## Use Cases

Jupyter Enterprise Gateway makes possible the following uses cases:

* A company with many data analysts and a large Yarn cluster have found their Kernel Gateway server 
to be a bottleneck  due to the size of each kernel (spark driver) process.  By deploying Enterprise Gateway, 
their kernels can be launched as managed resources within Yarn, distributing the resource-intensive 
driver processes across the Yarn cluster.
* ...
