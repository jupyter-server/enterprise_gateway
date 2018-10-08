# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

FROM jupyterhub/k8s-singleuser-sample:0.7.0

# pip packages
RUN pip install --upgrade pip
RUN pip install setuptools --ignore-installed --upgrade

ENV NBGITPULLER_APP=lab

# Do the pip installs as the unprivileged notebook user
USER jovyan

# Install Lab and NB2KG. Enable NB2KG extension.  Lab extension is optionally enabled at runtime.
RUN pip install --upgrade jupyterlab nb2kg && \
    jupyter serverextension enable --py nb2kg --sys-prefix

# Run with remote kernel managers
ENTRYPOINT ["/usr/local/bin/start-nb2kg.sh"]

# Add local files as late as possible to avoid cache busting
ADD jupyter_notebook_config.py /etc/jupyter/jupyter_notebook_config.py
ADD start-nb2kg.sh /usr/local/bin/start-nb2kg.sh