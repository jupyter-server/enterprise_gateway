# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

FROM jupyter/minimal-notebook

# pip packages
RUN pip install --upgrade pip
RUN pip install setuptools --ignore-installed --upgrade

# Do the pip installs as the unprivileged notebook user
USER jovyan

# Install Lab and NB2KG. Enable NB2KG extension.  Lab extension is optionally enabled at runtime.
RUN pip install jupyterlab nb2kg && \
    jupyter serverextension enable --py nb2kg --sys-prefix

ADD start-nb2kg.sh /usr/local/share/jupyter/

# Run with remote kernel managers
ENTRYPOINT ["/usr/local/share/jupyter/start-nb2kg.sh"]
CMD ["notebook"]

WORKDIR /home/jovyan/work
