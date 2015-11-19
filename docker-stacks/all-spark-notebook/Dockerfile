# Copyright (c) Jupyter Development Team.
FROM jupyter/all-spark-notebook:dbb9c7b50531

MAINTAINER Jupyter Project <jupyter@googlegroups.com>

# Install Kernel Gateway
RUN pip install jupyter_kernel_gateway==0.1.0

# Configure container startup
ENTRYPOINT ["tini", "--"]
CMD ["start.sh"]

# Add local files as late as possible to avoid cache busting
COPY start.sh /usr/local/bin/
COPY jupyter_kernel_gateway_config.py /home/$NB_USER/.jupyter/
RUN chown -R $NB_USER:users /home/$NB_USER/.jupyter