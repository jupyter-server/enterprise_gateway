# Ubuntu:xenial
FROM tensorflow/tensorflow:1.11.0-gpu-py3

RUN pip install pycrypto

COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

COPY bootstrap-kernel.sh /usr/local/bin/

USER root

RUN adduser --system --uid 1000 --gid 100 jovyan && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/share/jupyter

USER jovyan