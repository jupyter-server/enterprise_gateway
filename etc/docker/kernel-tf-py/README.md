This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster that can perform Tensorflow operations. It is built on `jupyter/tensorflow-notebook:2023-10-20` (from the [jupyter/docker-stacks](https://github.com/jupyter/docker-stacks/tree/main/images/tensorflow-notebook) project); refer to that image's release notes for the bundled TensorFlow version.

# What it Gives You

- IPython kernel support supplemented with Tensorflow functionality (and debugger)

# Basic Use

Deploy [enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) per its instructions and configured to the appropriate environment.

Launch a gateway-enabled Jupyter Notebook application against the Enterprise Gateway instance and pick the desired kernel to use in your notebook.

For more information, check our [repo](https://github.com/jupyter-server/enterprise_gateway) and [docs](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/).

# Pinned dependencies

This image installs the IPython kernel with the following upper bounds, applied to keep kernel runtime behavior consistent across the kernel image fleet:

- `ipykernel<7` — ipykernel 7.x rewrote the asyncio integration in a way that prevents kernels from transitioning to the `idle` state under Enterprise Gateway's process-proxy model.
- `jupyter_client<9`, `jupyter_server<3`, `pyzmq<28` — held in lockstep with `ipykernel<7` so the Jupyter messaging layer stays on a known-compatible API surface across all kernel images.

Bumping any of these caps requires re-running `make itest-yarn-debug` against the integration suite to confirm `test_interrupt`, `test_restart`, and the kernel idle/busy transitions still behave correctly.
