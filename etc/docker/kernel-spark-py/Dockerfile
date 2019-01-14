FROM elyra/spark-py:v2.4.0

RUN apk del python3 && \
    apk add --no-cache build-base libffi-dev openssl-dev python-dev python3-dev && \
    pip3 install cffi ipykernel ipython jupyter_client pycrypto && \
    pip install cffi ipykernel ipython jupyter_client pycrypto && \
    rm -r /root/.cache

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin

RUN adduser -S -u 1000 -G users jovyan && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers /opt/spark/work-dir

USER jovyan

ENV KERNEL_LANGUAGE python
