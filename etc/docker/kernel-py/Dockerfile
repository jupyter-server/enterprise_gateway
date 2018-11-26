# Ubuntu 18.04.1 LTS Bionic
FROM jupyter/scipy-notebook:61d8aaedaeaf

RUN pip install pycrypto

COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

COPY bootstrap-kernel.sh /usr/local/bin/

USER root

RUN chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/share/jupyter

USER jovyan
