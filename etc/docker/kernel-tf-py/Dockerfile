# Ubuntu:Bionic
FROM jupyter/tensorflow-notebook:04f7f60d34a6

ENV KERNEL_LANGUAGE python

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

CMD [ "/usr/local/bin/bootstrap-kernel.sh" ]
