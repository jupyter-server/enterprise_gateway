This image enables the use of an IPython kernel launched from [Jupyter Enterprise Gateway](https://jupyter-enterprise-gateway.readthedocs.io/en/latest/) within a Kubernetes or Docker Swarm cluster that can perform Tensorflow operations. It is currently built on [tensorflow/tensorflow:2.20.0-gpu](https://hub.docker.com/r/tensorflow/tensorflow/) deriving from the [tensorflow](https://github.com/tensorflow/tensorflow) project.

# Base image

Built on `tensorflow/tensorflow:2.20.0-gpu`, which provides:

- Ubuntu 22.04
- Python 3.10
- CUDA 12.3
- TensorFlow 2.20 with GPU support

The image installs `python3-pip` from Ubuntu's apt repositories because `apt-get install python3-dev` shadows the `pip` shipped inside the TensorFlow base image; `python3 -m pip` is then used for all subsequent Python installs in the Dockerfile.

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
