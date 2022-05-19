Users Guide
===========

Because Enterprise Gateway is a headless web server, it is typically accessed from other applications like JupyterLab and Jupyter Notebook.

.. admonition:: Use cases

    - *As a data scientist, I want to run my notebook using the Enterprise Gateway such that I can free up resources on my own laptop and leverage my company's large Hadoop YARN cluster to run my compute-intensive operations.*

    - *As a student, my Data Science 101 course is leveraging GPUs in our experiments.  Since GPUs are expensive, we must share resources within the university's compute cluster and configure our Notebooks to leverage the department's Enterprise Gateway server, which can then spawn container-based kernels that have access to a GPU on Kubernetes.*

The following assumes an Enterprise Gateway server has been configured and deployed.  Please consult the `operators <../operators/index.html>`_ documentation to deploy and configure the Enterprise Gateway server.

.. note::
  There are two primary client applications that can use Enterprise Gateway, JupyterLab running on Jupyter Server and Jupyter Notebook.  When a reference to a *Jupyter server* (lowercase 'server') or *the server* is made, the reference applies to both Jupyter Server and Jupyter Notebook.  Generally speaking, the client-side behaviors are identical between the two, although references to Jupyter Server are preferred since it's more current.  If anything is different, that difference will be noted, otherwise, please assume discussion of the two are interchangeable.

.. toctree::
   :maxdepth: 1
   :name: users

   installation
   connecting-to-eg
   client-config
   kernel-envs
..
   other clients (nbclient, papermill)
