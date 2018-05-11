FROM kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY bootstrap-kernel.sh /usr/local/share/jupyter/kernels