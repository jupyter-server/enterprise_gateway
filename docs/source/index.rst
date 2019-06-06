Jupyter Enterprise Gateway
==========================

`Jupyter Enterprise Gateway <https://github.com/jupyter/enterprise_gateway>`_ is a web server (built directly
on `Jupyter Kernel Gateway <http://jupyter-kernel-gateway.readthedocs.io/en/latest/>`_) that enables the ability to
launch kernels on behalf of remote notebooks throughout your enterprise compute cluster.  This enables better resource
management since the web server is no longer the single location for kernel activity which, in Big Data environments,
can result in large processes that together deplete your single node of its resources.

.. figure:: images/Scalability-Before-JEG.gif
   :align: center


By default, Jupyter runs kernels locally - potentially exhausting the server of resources

By leveraging the functionality of the
underlying resource management applications like Hadoop YARN, Kubernetes, etc., Jupyter Enterprise Gateway
distributes kernels across the compute cluster, dramatically increasing the number of simultaneously active kernels.

.. figure:: images/Scalability-After-JEG.gif
   :align: center

Jupyter Enterprise Gateway leverages local resource managers to distribute kernels

.. toctree::
   :maxdepth: 2
   :caption: User Documentation

   getting-started
   system-architecture
   getting-started-security
   getting-started-other-features
   use-cases

.. toctree::
   :maxdepth: 2
   :caption: Deployments

   kernel-local
   kernel-distributed
   kernel-yarn-cluster-mode
   kernel-yarn-client-mode
   kernel-spark-standalone
   kernel-kubernetes
   kernel-docker
   kernel-conductor

.. toctree::
   :maxdepth: 2
   :caption: Configuration

   config-options
   troubleshooting
   debug

.. toctree::
   :maxdepth: 2
   :caption: Contributor Documentation

   contrib
   devinstall
   docker
   roadmap

.. toctree::
   :maxdepth: 2
   :caption: Community Documentation

   Jupyter mailing list <https://groups.google.com/forum/#!forum/jupyter>
   Jupyter website <https://jupyter.org>
   Stack Overflow - Jupyter <https://stackoverflow.com/questions/tagged/jupyter>
   Stack Overflow - Jupyter-notebook <https://stackoverflow.com/questions/tagged/jupyter-notebook>

