FROM elyra/spark:v2.4.0

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin

RUN adduser -S -u 1000 -G users jovyan && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers /opt/spark/work-dir

USER jovyan
ENV KERNEL_LANGUAGE scala
CMD /usr/local/bin/bootstrap-kernel.sh


