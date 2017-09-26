## Use Cases

Jupyter Enterprise Gateway makes possible the following uses cases:

* A company with many data analysts and a large Yarn cluster have found their Kernel Gateway server 
to be a bottleneck  due to the size of each kernel (spark driver) process.  By deploying Enterprise Gateway, 
their kernels can be launched as managed resources within Yarn, distributing the resource-intensive 
driver processes across the Yarn cluster.

* A company recently plan to deploy their Spark notebook services with Jupyter Enterprise Gateway in a cluster 
where Mesos is the resource manager instead of YARN that currently on the open source side. After reading the 
documentation on how to add new a ProcessProxy class required as an interface by the resource manager components 
in gateway, they implement, deploy and configure MesosProcessProxy that referenced by their kernelspecs and now
they can launch kernels within their Mesos cluster. 

* ...
