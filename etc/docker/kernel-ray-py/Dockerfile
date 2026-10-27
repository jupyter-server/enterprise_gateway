# Ray with Python 3.11 (CPU); RAY_VERSION selects both the base image and
# the matching ray[data] pin below
ARG RAY_VERSION=2.58.0
ARG BASE_CONTAINER=rayproject/ray:${RAY_VERSION}-extra-py311-cpu
FROM $BASE_CONTAINER
ARG RAY_VERSION

# Add debugger support
# ipykernel 7 has asyncio rewrite affecting kernels to become idle
# jupyter_client/server/pyzmq capped to converge with the rest of the fleet
RUN pip install --upgrade --no-cache-dir \
    "ray[data]==${RAY_VERSION}" \
    cffi \
    future \
    pycryptodomex \
    "ipykernel<7" \
    "jupyter_client<9" \
    "jupyter_server<3" \
    "pyzmq<28"

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
