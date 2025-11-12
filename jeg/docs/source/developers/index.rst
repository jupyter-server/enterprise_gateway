Developers Guide
================

These pages target *developers* writing applications against the REST API, authoring process proxies for other resource managers, or integrating applications with remote kernel functionality.

.. admonition:: Use cases

    - *As a developer, I want to explore supporting a different resource manager with Enterprise Gateway, by implementing a new `ProcessProxy` class such that I can easily take advantage of specific functionality provided by the resource manager.*
    - *As a developer, I want to extend the `nbclient` application to use a `KernelManager` that can leverage remote kernels spawned from Enterprise Gateway.*
    - *As a developer, I want to easily integrate the ability to launch remote kernels with existing platforms, so I can leverage my compute cluster in a customizable way.*
    - *As a developer, I am currently using Golang and need to implement a kernel launcher to allow the Go kernel I use to run remotely in my Kubernetes cluster.*
    - *As a developer, I'd like to extend some of the kernel container images and, eventually, create my own to better enable the data scientists I support.*
    - *As a developer, I need want to author my own Kernel-as-a-Service application.*

.. toctree::
   :maxdepth: 1
   :name: developers

   dev-process-proxy
   kernel-launcher
   kernel-specification
   custom-images
   kernel-library
   kernel-manager
   rest-api
