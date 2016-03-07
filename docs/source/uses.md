## Interesting Uses

These are just some of the interesting deployments by current users of the
Jupyter Kernel Gateway:

* Attach a local Jupyter Notebook server to a compute cluster in the cloud 
  running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use 
  kernels (e.g., dashboards using 
  [jupyter-js-services](https://github.com/jupyter/jupyter-js-services))
* Scale kernels independently from clients (e.g., via 
  [tmpnb](https://github.com/jupyter/tmpnb), [Binder](https://mybinder.org),
  or your favorite cluster manager)
* Create microservices from notebooks via 
  [`notebook-http` mode](#notebook-http-mode)

### Example use with tmpnb 

The following diagram shows how `tmpnb` might deploy Jupyer Kernel Gateway
and kernel containers:

![Example diagram of how `tmpnb` might deploy kernel gateway + kernel containers](../../etc/tmpnb_kernel_gateway.png)

### Demos
See the [jupyter/kernel_gateway_demos](https://github.com/jupyter/kernel_gateway_demos) 
repository for additional ideas.
