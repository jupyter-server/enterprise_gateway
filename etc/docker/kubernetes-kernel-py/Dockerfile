FROM kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client pycrypto

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY bootstrap-kernel.sh spark-exec.sh /etc/

RUN addgroup -S -g 620 eg-kernel && adduser -S -u 620 -G eg-kernel eg-kernel && \
    chown eg-kernel.eg-kernel /etc/bootstrap-kernel.sh /etc/spark-exec.sh && \
	chmod 0755 /etc/bootstrap-kernel.sh /etc/spark-exec.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter /opt/spark/work-dir

USER eg-kernel

CMD /etc/spark-exec.sh
