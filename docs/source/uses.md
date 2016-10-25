## Use Cases

The Jupyter Kernel Gateway makes possible the following novel uses of kernels:

* Attach a local Jupyter Notebook server to a compute cluster in the cloud 
  running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use 
  kernels (e.g., dashboards using 
  [jupyter-js-services](https://github.com/jupyter/jupyter-js-services))
* Scale kernels independently from clients (e.g., via 
  [tmpnb](https://github.com/jupyter/tmpnb), [Binder](http://mybinder.org/),
  or your favorite cluster manager)
* Create microservices from notebooks via 
  [`notebook-http` mode](notebook-http-mode)

The following diagram shows how you might use `tmpnb` to deploy a pool of kernel gateway instances in Docker containers to support on-demand interactive compute:

![Example diagram of tmpnb deployment of kernel gateway instances](images/tmpnb_kernel_gateway.png)

For more inspiration, see the [jupyter/kernel_gateway_demos](https://github.com/jupyter/kernel_gateway_demos).
