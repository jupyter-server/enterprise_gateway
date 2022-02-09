# Related Resources

Here are some resources related to the Jupyter Enterprise Gateway project. 

* [Jupyter Kernel Gateway Github Repo](https://github.com/jupyer-server/kernel_gateway) - the source code for Kernel Gateway - which supports local kernels and notebook-hosted end-points.
* [Jupyter Server Github Repo](https://github.com/jupyter-server/jupyter_server) - the source code for the Jupyter Server.  Many of the Enterprise Gateway's handlers and kernel management classes either _are_ or are derived from the Jupyter Server classes.
* [Jupyter Notebook Github Repo](https://github.com/jupyter/notebook>) - the source code for the classic Notebook from which the gateways and Jupyter Server were derived.
* [Jupyter Client Github Repo](https://github.com/jupyter/jupyter_client>) - the source code for the base kernel lifecycle management and message classes.  Enterprise Gateway extends the `KernelManager` classes of `jupyter_client`.
