FROM tensorflow/tensorflow:1.9.0-gpu-py3

RUN pip install pycrypto

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY bootstrap-kernel.sh /etc/

RUN addgroup --system --gid 620 eg-kernel && adduser --system --uid 620 --gid 620 eg-kernel && \
    chown eg-kernel.eg-kernel /etc/bootstrap-kernel.sh && \
	chmod 0755 /etc/bootstrap-kernel.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter

USER eg-kernel

