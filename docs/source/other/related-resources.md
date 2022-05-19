# Related Resources

Here are some resources related to the Jupyter Enterprise Gateway project.

- [Jupyter.org](https://jupyter.org)
- [Jupyter Server Team Compass](https://github.com/jupyter-server/team-compass#jupyter-server-team-compass)
- [Jupyter Calendar - Community Meetings](https://docs.jupyter.org/en/latest/community/content-community.html#jupyter-community-meetings)
- [Jupyter Community Discourse Forum](https://discourse.jupyter.org/)
- [Jupyter Kernel Gateway Github Repo](https://github.com/jupyter-server/kernel_gateway) - the source code for Kernel Gateway - which supports local kernels and notebook-hosted end-points.
- [Jupyter Server Github Repo](https://github.com/jupyter-server/jupyter_server) - the source code for the Jupyter Server. Many of the Enterprise Gateway's handlers and kernel management classes either _are_ or are derived from the Jupyter Server classes.
- [Jupyter Notebook Github Repo](https://github.com/jupyter/notebook) - the source code for the classic Notebook from which the gateways and Jupyter Server were derived.
- [Jupyter Client Github Repo](https://github.com/jupyter/jupyter_client) - the source code for the base kernel lifecycle management and message classes. Enterprise Gateway extends the `KernelManager` classes of `jupyter_client`.
