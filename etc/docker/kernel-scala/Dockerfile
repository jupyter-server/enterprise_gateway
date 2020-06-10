FROM elyra/spark:v2.4.5

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

# Create/setup the jovyan system user
RUN adduser --system -uid 1000 jovyan --ingroup users && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0777 /opt/spark/work-dir && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan
ENV KERNEL_LANGUAGE scala
CMD /usr/local/bin/bootstrap-kernel.sh
