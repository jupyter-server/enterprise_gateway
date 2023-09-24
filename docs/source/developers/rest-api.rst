Using the REST API
===============================

The REST API is used to author new applications that need to interact with
Enterprise Gateway.  Generally speaking, only the ``/api/kernels`` and
``/api/kernelspecs`` endpoints are used.  The ``/api/sessions`` endpoint *can*
be used to manage a kernel's lifecycle, but it is not necessary.  For example,
while the Jupyter Notebook and JupyterLab applications start kernels using
``/api/sessions``, the only interaction they perform with Enterprise Gateway is
via the ``/api/kernelspecs`` to retrieve a list of available kernel
specifications, and ``/api/kernels`` to start, stop, interrupt and restart a
kernel.  The "session" remains on the client.

General sequence
----------------
Here's the general sequence of events to implement a REST-based application to *discover*, *start*, *execute code*, *interrupt*, and *shutdown* a kernel.  To demonstrate each call, we'll use `curl` against a running Enterprise Gateway server at ``http://my-gateway-server.com:8888``.

Kernel discovery
~~~~~~~~~~~~~~~~
Issue a `GET` request against the ``/api/kernelspecs`` endpoint to discover
available kernel specifications. Each entry corresponds to a ``kernel.json``
file located in a directory that corresponds to the kernel's name.  This *name*
is what will be used in the subsequent start request.

The response is a JSON object where the ``default`` is a string specifying the
name of the default kernel.  This kernel specification will be used if the
start request (e.g., ``POST /api/kernels``) does not specify a kernel name in
its JSON body.

The other key in the response is `kernelspecs` and consists of a JSON indexed
by kernel name with a value corresponding to the corresponding ``kernel.json``
in addition to any *resources* associated with the kernel.  These are typically
the icon filenames to be used by the front-end application.

.. code-block:: console

    curl http://my-gateway-server.com:8888/api/kernelspecs

.. raw:: html

   <details>
   <summary><a><span style="font-family:'Courier New'">GET /api/kernelspecs</span> response</a></summary>

.. code-block:: json

    {
      "default": "python3",
      "kernelspecs": {
        "python3": {
          "name": "python3",
          "spec": {
            "argv": [
              "/usr/bin/env",
              "/opt/anaconda2/envs/py3/bin/python",
              "-m",
              "ipykernel_launcher",
              "-f",
              "{connection_file}"
            ],
            "display_name": "Python 3",
            "language": "python",
            "interrupt_mode": "signal",
            "metadata": {}
          },
          "resources": {
            "logo-32x32": "/kernelspecs/python3/logo-32x32.png",
            "logo-64x64": "/kernelspecs/python3/logo-64x64.png"
          }
        },
        "ir": {
          "name": "ir",
          "spec": {
            "argv": [
              "R",
              "--slave",
              "-e",
              "IRkernel::main()",
              "--args",
              "{connection_file}"
            ],
            "env": {},
            "display_name": "R",
            "language": "R",
            "interrupt_mode": "signal",
            "metadata": {}
          },
          "resources": {
            "kernel.js": "/kernelspecs/ir/kernel.js",
            "logo-64x64": "/kernelspecs/ir/logo-64x64.png"
          }
        },
        "spark_r_yarn_client": {
          "name": "spark_r_yarn_client",
          "spec": {
            "argv": [
              "/usr/local/share/jupyter/kernels/spark_R_yarn_client/bin/run.sh",
              "--RemoteProcessProxy.kernel-id",
              "{kernel_id}",
              "--RemoteProcessProxy.response-address",
              "{response_address}",
              "--RemoteProcessProxy.public-key",
              "{public_key}",
              "--RemoteProcessProxy.port-range",
              "{port_range}",
              "--RemoteProcessProxy.spark-context-initialization-mode",
              "lazy"
            ],
            "env": {
              "SPARK_HOME": "/usr/hdp/current/spark2-client",
              "SPARK_OPTS": "--master yarn --deploy-mode client --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.sparkr.r.command=/opt/conda/lib/R/bin/Rscript ${KERNEL_EXTRA_SPARK_OPTS}",
              "LAUNCH_OPTS": ""
            },
            "display_name": "Spark - R (YARN Client Mode)",
            "language": "R",
            "interrupt_mode": "signal",
            "metadata": {
              "process_proxy": {
                "class_name": "enterprise_gateway.services.processproxies.distributed.DistributedProcessProxy"
              }
            }
          },
          "resources": {
            "kernel.js": "/kernelspecs/spark_r_yarn_client/kernel.js",
            "logo-64x64": "/kernelspecs/spark_r_yarn_client/logo-64x64.png"
          }
        },
        "spark_r_yarn_cluster": {
          "name": "spark_r_yarn_cluster",
          "spec": {
            "argv": [
              "/usr/local/share/jupyter/kernels/spark_R_yarn_cluster/bin/run.sh",
              "--RemoteProcessProxy.kernel-id",
              "{kernel_id}",
              "--RemoteProcessProxy.response-address",
              "{response_address}",
              "--RemoteProcessProxy.public-key",
              "{public_key}",
              "--RemoteProcessProxy.port-range",
              "{port_range}",
              "--RemoteProcessProxy.spark-context-initialization-mode",
              "eager"
            ],
            "env": {
              "SPARK_HOME": "/usr/hdp/current/spark2-client",
              "SPARK_OPTS": "--master yarn --deploy-mode cluster --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false --conf spark.yarn.am.waitTime=1d --conf spark.yarn.appMasterEnv.PATH=/opt/conda/bin:$PATH --conf spark.sparkr.r.command=/opt/conda/lib/R/bin/Rscript ${KERNEL_EXTRA_SPARK_OPTS}",
              "LAUNCH_OPTS": ""
            },
            "display_name": "Spark - R (YARN Cluster Mode)",
            "language": "R",
            "interrupt_mode": "signal",
            "metadata": {
              "process_proxy": {
                "class_name": "enterprise_gateway.services.processproxies.yarn.YarnClusterProcessProxy"
              }
            }
          },
          "resources": {
            "kernel.js": "/kernelspecs/spark_r_yarn_cluster/kernel.js",
            "logo-64x64": "/kernelspecs/spark_r_yarn_cluster/logo-64x64.png"
          }
        },
        "spark_python_yarn_client": {
          "name": "spark_python_yarn_client",
          "spec": {
            "argv": [
              "/usr/local/share/jupyter/kernels/spark_python_yarn_client/bin/run.sh",
              "--RemoteProcessProxy.kernel-id",
              "{kernel_id}",
              "--RemoteProcessProxy.response-address",
              "{response_address}",
              "--RemoteProcessProxy.public-key",
              "{public_key}",
              "--RemoteProcessProxy.port-range",
              "{port_range}",
              "--RemoteProcessProxy.spark-context-initialization-mode",
              "lazy"
            ],
            "env": {
              "SPARK_HOME": "/usr/hdp/current/spark2-client",
              "PYSPARK_PYTHON": "/opt/conda/bin/python",
              "PYTHONPATH": "${HOME}/.local/lib/python3.8/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip",
              "SPARK_OPTS": "--master yarn --deploy-mode client --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} ${KERNEL_EXTRA_SPARK_OPTS}",
              "LAUNCH_OPTS": ""
            },
            "display_name": "Spark - Python (YARN Client Mode)",
            "language": "python",
            "interrupt_mode": "signal",
            "metadata": {
              "process_proxy": {
                "class_name": "enterprise_gateway.services.processproxies.distributed.DistributedProcessProxy"
              },
              "debugger": true
            }
          },
          "resources": {
            "logo-64x64": "/kernelspecs/spark_python_yarn_client/logo-64x64.png"
          }
        },
        "spark_python_yarn_cluster": {
          "name": "spark_python_yarn_cluster",
          "spec": {
            "argv": [
              "/usr/local/share/jupyter/kernels/spark_python_yarn_cluster/bin/run.sh",
              "--RemoteProcessProxy.kernel-id",
              "{kernel_id}",
              "--RemoteProcessProxy.response-address",
              "{response_address}",
              "--RemoteProcessProxy.public-key",
              "{public_key}",
              "--RemoteProcessProxy.port-range",
              "{port_range}",
              "--RemoteProcessProxy.spark-context-initialization-mode",
              "lazy"
            ],
            "env": {
              "SPARK_HOME": "/usr/hdp/current/spark2-client",
              "PYSPARK_PYTHON": "/opt/conda/bin/python",
              "PYTHONPATH": "${HOME}/.local/lib/python3.8/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip",
              "SPARK_OPTS": "--master yarn --deploy-mode cluster --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false --conf spark.yarn.appMasterEnv.PYTHONUSERBASE=/home/${KERNEL_USERNAME}/.local --conf spark.yarn.appMasterEnv.PYTHONPATH=${HOME}/.local/lib/python3.8/site-packages:/usr/hdp/current/spark2-client/python:/usr/hdp/current/spark2-client/python/lib/py4j-0.10.6-src.zip --conf spark.yarn.appMasterEnv.PATH=/opt/conda/bin:$PATH ${KERNEL_EXTRA_SPARK_OPTS}",
              "LAUNCH_OPTS": ""
            },
            "display_name": "Spark - Python (YARN Cluster Mode)",
            "language": "python",
            "interrupt_mode": "signal",
            "metadata": {
              "process_proxy": {
                "class_name": "enterprise_gateway.services.processproxies.yarn.YarnClusterProcessProxy"
              },
              "debugger": true
            }
          },
          "resources": {
            "logo-64x64": "/kernelspecs/spark_python_yarn_cluster/logo-64x64.png"
          }
        },
        "spark_scala_yarn_client": {
          "name": "spark_scala_yarn_client",
          "spec": {
            "argv": [
              "/usr/local/share/jupyter/kernels/spark_scala_yarn_client/bin/run.sh",
              "--RemoteProcessProxy.kernel-id",
              "{kernel_id}",
              "--RemoteProcessProxy.response-address",
              "{response_address}",
              "--RemoteProcessProxy.public-key",
              "{public_key}",
              "--RemoteProcessProxy.port-range",
              "{port_range}",
              "--RemoteProcessProxy.spark-context-initialization-mode",
              "lazy"
            ],
            "env": {
              "SPARK_HOME": "/usr/hdp/current/spark2-client",
              "__TOREE_SPARK_OPTS__": "--master yarn --deploy-mode client --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} ${KERNEL_EXTRA_SPARK_OPTS}",
              "__TOREE_OPTS__": "--alternate-sigint USR2",
              "LAUNCH_OPTS": "",
              "DEFAULT_INTERPRETER": "Scala"
            },
            "display_name": "Spark - Scala (YARN Client Mode)",
            "language": "scala",
            "interrupt_mode": "signal",
            "metadata": {
              "process_proxy": {
                "class_name": "enterprise_gateway.services.processproxies.distributed.DistributedProcessProxy"
              }
            }
          },
          "resources": {
            "logo-64x64": "/kernelspecs/spark_scala_yarn_client/logo-64x64.png"
          }
        },
        "spark_scala_yarn_cluster": {
          "name": "spark_scala_yarn_cluster",
          "spec": {
            "argv": [
              "/usr/local/share/jupyter/kernels/spark_scala_yarn_cluster/bin/run.sh",
              "--RemoteProcessProxy.kernel-id",
              "{kernel_id}",
              "--RemoteProcessProxy.response-address",
              "{response_address}",
              "--RemoteProcessProxy.public-key",
              "{public_key}",
              "--RemoteProcessProxy.port-range",
              "{port_range}",
              "--RemoteProcessProxy.spark-context-initialization-mode",
              "lazy"
            ],
            "env": {
              "SPARK_HOME": "/usr/hdp/current/spark2-client",
              "__TOREE_SPARK_OPTS__": "--master yarn --deploy-mode cluster --name ${KERNEL_ID:-ERROR__NO__KERNEL_ID} --conf spark.yarn.submit.waitAppCompletion=false --conf spark.yarn.am.waitTime=1d ${KERNEL_EXTRA_SPARK_OPTS}",
              "__TOREE_OPTS__": "--alternate-sigint USR2",
              "LAUNCH_OPTS": "",
              "DEFAULT_INTERPRETER": "Scala"
            },
            "display_name": "Spark - Scala (YARN Cluster Mode)",
            "language": "scala",
            "interrupt_mode": "signal",
            "metadata": {
              "process_proxy": {
                "class_name": "enterprise_gateway.services.processproxies.yarn.YarnClusterProcessProxy"
              }
            }
          },
          "resources": {
            "logo-64x64": "/kernelspecs/spark_scala_yarn_cluster/logo-64x64.png"
          }
        }
      }
    }

.. raw:: html

   </details>

Kernel start
~~~~~~~~~~~~~~~~
A kernel is started by issuing a ``POST`` request against the ``/api/kernels``
endpoint.  The JSON body can take a ``name``, indicating the kernel to start,
and an ``env`` JSON, corresponding to environment variables to set in the
kernel's environment.

In this example, we will start the ``spark_python_yarn_cluster`` kernel with a ``KERNEL_USERNAME`` environment variable of ``jovyan``.

.. code-block:: console

    curl -X POST -i 'http://my-gateway-server.com:8888/api/kernels' --data '{ "name": "spark_python_yarn_cluster", "env": { "KERNEL_USERNAME": "jovyan" }}'

.. raw:: html

   <details>
   <summary><a><span style="font-family:'Courier New'">POST /api/kernels</span> response</a></summary>

.. code-block:: json

    {
      "id": "f88bdc84-04c6-4021-963d-6811a61eca18",
      "name": "spark_python_yarn_cluster",
      "last_activity": "2022-02-12T00:40:45.080107Z",
      "execution_state": "starting",
      "connections": 0
    }

.. raw:: html

   </details>

Kernel code execution
~~~~~~~~~~~~~~~~~~~~~
Upgrading the connection to a websocket and issuing code against that websocket is currently beyond the knowledge of our maintainers.  For this aspect of this discussion we will refer you to our Python `GatewayClient class <https://github.com/jupyter-server/enterprise_gateway/blob/54c8e31d9b17418f35454b49db691d2ce5643c22/enterprise_gateway/client/gateway_client.py#L22>`_ that we use in our integration tests.

.. note::

   The name ``GatewayClient`` in our ``enterprise_gateway/client`` subdirectory is not to be confused with the ``GatewayClient`` class defined in the client applications in Jupyter Server and Notebook.  In addition, the internal test class ``KernelClient`` is not to be confused with the ``KernelClient`` that lives in the ``jupyter_client`` package.

Kernel interrupt
~~~~~~~~~~~~~~~~
A kernel is interrupted by issuing a ``POST`` request against the ``/api/kernels/<kernel_id>/interrupt`` endpoint.

In this example, we will interrupt the ``spark_python_yarn_cluster`` kernel with ID ``f88bdc84-04c6-4021-963d-6811a61eca18`` that was started previously.

.. note::

   Restarting a kernel is nearly identical to interrupting a kernel; just replace ``interrupt`` in the endpoint with ``restart``.

.. code-block:: console

    curl -X POST -i 'http://ymy-gateway-server.com:8888/api/kernels/f88bdc84-04c6-4021-963d-6811a61eca18/interrupt'

An expected response of ``Status Code`` equal ``204`` (No Content) is returned.  (The expected response for ``restart`` is ``200`` (OK).)


Kernel shutdown
~~~~~~~~~~~~~~~~
A kernel is shutdown by issuing a ``DELETE`` request against the ``/api/kernels/<kernel_id>`` endpoint.

In this example, we will shutdown the ``spark_python_yarn_cluster`` kernel with ID ``f88bdc84-04c6-4021-963d-6811a61eca18`` that was started previously.

.. code-block:: console

    curl -X DELETE -i 'http://my-gateway-server.com:8888/api/kernels/f88bdc84-04c6-4021-963d-6811a61eca18'

An expected response of ``Status Code`` equal ``204`` (No Content) is returned.

OpenAPI Specification
~~~~~~~~~~~~~~~~~~~~~
Here's the current `OpenAPI <https://www.openapis.org/>`_ specification available from Enterprise Gateway.  An interactive version is available `here <https://petstore.swagger.io/?url=https://raw.githubusercontent.com/jupyter-server/enterprise_gateway/main/enterprise_gateway/services/api/swagger.yaml>`_.

.. openapi:: ../../../enterprise_gateway/services/api/swagger.yaml
