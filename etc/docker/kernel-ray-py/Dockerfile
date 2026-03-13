# Ray 2.50.0 with Python 3.11
# rayproject/ray:2.50.0.714bc0-extra-py311-cpu
ARG BASE_CONTAINER=rayproject/ray:2.50.0.714bc0-extra-py311-cpu
FROM $BASE_CONTAINER

# Add debugger support
RUN pip install --upgrade --no-cache-dir ipykernel

RUN pip install --upgrade --no-cache-dir --upgrade \
    "jupyter_client>=6.1,<7" \
    "jupyter_server>=1.7,<2" \
    "pyzmq>=20.0.0,<25" \
    "ray[data]==2.50.0" \
    ipykernel \
    cffi \
    future \
    pycryptodomex

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

USER root

RUN apt-get update && apt-get install -yq --no-install-recommends \
    libkrb5-dev \
    iputils-ping \
    telnet \
    netcat-openbsd \
    net-tools \
    iproute2 \
    dnsutils \
    curl \
    less \
    && rm -rf /var/lib/apt/lists/*

# Set up permissions for ray user (Ray base image uses 'ray' user)
RUN chown ray:users /usr/local/bin/bootstrap-kernel.sh && \
    chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
    chown -R ray:users /usr/local/bin/kernel-launchers

USER ray

ENV KERNEL_LANGUAGE=python
ENV RAY_HOME=/home/ray

WORKDIR /home/ray

# Disble healthcheck inherited from notebook image
HEALTHCHECK NONE


CMD /usr/local/bin/bootstrap-kernel.sh
