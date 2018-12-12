# Ubuntu 18.04.1 LTS Bionic
FROM jupyter/scipy-notebook:61d8aaedaeaf

RUN pip install pycrypto

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin

USER root

RUN chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan
ENV KERNEL_LANGUAGE python
CMD /usr/local/bin/bootstrap-kernel.sh
