# Ubuntu:Bionic
# TensorFlow 2.4.0
ARG BASE_CONTAINER=jupyter/tensorflow-notebook:2023-10-20

FROM $BASE_CONTAINER

ENV KERNEL_LANGUAGE=python

# ipykernel 7 has asyncio rewrite affecting kernels to become idle
# jupyter_client/server/pyzmq capped to converge with the rest of the fleet
RUN pip install --upgrade \
    "ipykernel<7" \
    "jupyter_client<9" \
    "jupyter_server<3" \
    "pyzmq<28"

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

RUN conda install --quiet --yes \
    pillow \
    future \
    pycryptodomex && \
    fix-permissions $CONDA_DIR

USER root

RUN chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan

# Disble healthcheck inherited from notebook image
HEALTHCHECK NONE

CMD [ "/usr/local/bin/bootstrap-kernel.sh" ]
