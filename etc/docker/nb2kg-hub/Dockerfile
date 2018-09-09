# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

FROM jupyterhub/k8s-singleuser-sample:0.7.0

# Do the pip installs as the unprivileged notebook user
USER $NB_USER

# Install NB2KG
RUN pip install --upgrade nb2kg && \
    jupyter serverextension enable --py nb2kg --sys-prefix
