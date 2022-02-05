Documentation for Users
=======================

Jupyter Enterprise Gateway is a headless web server that is typically accessed from applications like JupyterLab and Jupyter Notebook.  For this section, those using Enterprise Gateway from JupyterLab or Jupyter Notebook are considered *users*, while those configuring and deploying Enterprise Gateway directly are considered *operators*.

The following assumes an Enterprise Gateway server has been configured and deployed.  Please consult the :ref:`operators <operators>` documentation to install, configure, and deploy the Enterprise Gateway server.

.. note::
    This section of the documentation discusses the *client* side of things.  There are two primary client applications that can use Enterprise Gateway, JupyterLab running on Jupyter Server and Jupyter Notebook.  When a reference to a *Jupyter server* (lowercase 'server') or *the server* is made, the reference applies to both Jupyter Server and Jupyter Notebook.  Generally speaking, the client-side behaviors are identical between the two, although references to Jupyter Server are preferred since it's more current.  If anything is different, that difference will be noted, otherwise, please assume discussion of the two are interchangeable.

**Use cases:**

- As a data scientist, I want to run my notebook using the Enterprise Gateway such that I can free up resources on my own laptop and leverage my company's large YARN cluster to run my compute-intensive jobs.


.. toctree::
   :caption: Users
   :maxdepth: 2
   :name: users

   use-cases
   installation
   connecting-to-eg
   client-config
   kernel-envs
   other clients (nbclient, papermill)

