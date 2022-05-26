ARG HUB_ORG
ARG SPARK_VERSION

# TODO: Restore usage of SPARK_VERSION ARG once https://github.com/jupyter/enterprise_gateway/pull/867 is merged
ARG BASE_CONTAINER=$HUB_ORG/spark:v$SPARK_VERSION
FROM $BASE_CONTAINER

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

USER root

# Create/setup the jovyan system user
RUN adduser --system -uid 1000 jovyan --ingroup users && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0777 /opt/spark/work-dir && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan
ENV KERNEL_LANGUAGE scala
CMD /usr/local/bin/bootstrap-kernel.sh
