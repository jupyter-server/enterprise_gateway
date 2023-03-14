# Ubuntu 18.04.1 LTS Bionic
ARG BASE_CONTAINER=jupyter/r-notebook:2023-03-13
FROM $BASE_CONTAINER

RUN conda install --quiet --yes \
    'r-argparse' \
    pycryptodomex && \
    conda clean --all && \
    fix-permissions $CONDA_DIR

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

# Switch back to root to modify ownerships
USER root

RUN apt-get update && apt-get install -y \
    less \
    curl \
    libkrb5-dev \
    && rm -rf /var/lib/apt/lists/*

RUN chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan

ENV KERNEL_LANGUAGE R

# Disble healthcheck inherited from notebook image
HEALTHCHECK NONE

CMD /usr/local/bin/bootstrap-kernel.sh
