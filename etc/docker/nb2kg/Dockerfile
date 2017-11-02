# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

FROM jupyter/minimal-notebook:fa77fe99579b

# pip packages
RUN pip install --upgrade pip
RUN pip install setuptools --ignore-installed --upgrade

# Do the pip installs as the unprivileged notebook user
USER jovyan

# Install dashboard layout and preview within Jupyter Notebook
RUN pip install "git+https://github.com/jupyter/kernel_gateway_demos.git#egg=nb2kg&subdirectory=nb2kg" && \
    jupyter serverextension enable --py nb2kg --sys-prefix

ADD start-nb2kg.sh /usr/local/share/jupyter/

# Run with remote kernel managers
CMD ["/usr/local/share/jupyter/start-nb2kg.sh"]

WORKDIR /home/jovyan/work
