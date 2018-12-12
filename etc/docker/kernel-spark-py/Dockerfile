FROM elyra/spark-py:v2.4.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client pycrypto

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin

RUN adduser -S -u 1000 -G users jovyan && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers /opt/spark/work-dir

USER jovyan

ENV KERNEL_LANGUAGE python
