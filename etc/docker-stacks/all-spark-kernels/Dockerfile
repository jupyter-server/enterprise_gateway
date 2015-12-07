# Copyright (c) Jupyter Development Team.
FROM jupyter/all-spark-notebook:dbb9c7b50531

MAINTAINER Jupyter Project <jupyter@googlegroups.com>

USER jovyan

# Install Kernel Gateway
RUN pip install jupyter_kernel_gateway==0.1.0

# Configure container startup
ENTRYPOINT ["tini", "--", "jupyter", "kernelgateway"]
CMD ["--KernelGatewayApp.ip=0.0.0.0"]