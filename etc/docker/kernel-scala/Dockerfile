ARG HUB_ORG
ARG SPARK_VERSION

# TODO: Restore usage of SPARK_VERSION ARG once https://github.com/jupyter/enterprise_gateway/pull/867 is merged
ARG BASE_CONTAINER=$HUB_ORG/spark:v$SPARK_VERSION
# Toree 0.5 ignores interrupts on Java 11, which elyra/spark ships, so the kernel (and Spark, through
# JAVA_HOME) runs on a Java 8 runtime copied from Temurin. Copying avoids apt: the base is Debian 11,
# whose package repositories are archived.
ARG JAVA8_CONTAINER=eclipse-temurin:8u512-b09-jre-noble

FROM $JAVA8_CONTAINER AS java8

FROM $BASE_CONTAINER

COPY --from=java8 /opt/java/openjdk /opt/java/openjdk-8
ENV JAVA_HOME=/opt/java/openjdk-8
ENV PATH=$JAVA_HOME/bin:$PATH

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

USER root

# Create/setup the jovyan system user
RUN adduser --system -uid 1000 jovyan --ingroup users && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0777 /opt/spark/work-dir && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan
ENV KERNEL_LANGUAGE=scala
CMD /usr/local/bin/bootstrap-kernel.sh
