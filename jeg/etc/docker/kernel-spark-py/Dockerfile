ARG HUB_ORG
ARG TAG

# Ubuntu 18.04.1 LTS Bionic
ARG BASE_CONTAINER=$HUB_ORG/kernel-py:$TAG
FROM $BASE_CONTAINER

ARG SPARK_VERSION

ENV SPARK_VER $SPARK_VERSION
ENV SPARK_HOME /opt/spark
ENV KERNEL_LANGUAGE python
ENV R_LIBS_USER $R_LIBS_USER:${SPARK_HOME}/R/lib
ENV PATH $PATH:$SPARK_HOME/bin

USER root

RUN dpkg --purge --force-depends ca-certificates-java \
    && apt-get update \
    && apt-get install -yq --no-install-recommends \
    ca-certificates \
    ca-certificates-java \
    openjdk-8-jdk \
    less \
    curl \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME /usr/lib/jvm/java
RUN ln -s $(readlink -f /usr/bin/javac | sed "s:/bin/javac::") ${JAVA_HOME}

# Download and install Spark
RUN curl -s https://archive.apache.org/dist/spark/spark-${SPARK_VER}/spark-${SPARK_VER}-bin-hadoop2.7.tgz | \
    tar -xz -C /opt && \
    ln -s ${SPARK_HOME}-${SPARK_VER}-bin-hadoop2.7 $SPARK_HOME

# Download entrypoint.sh from matching tag
RUN cd /opt/ && \
    wget https://raw.githubusercontent.com/apache/spark/v${SPARK_VER}/resource-managers/kubernetes/docker/src/main/dockerfiles/spark/entrypoint.sh && \
    chmod a+x /opt/entrypoint.sh && \
    sed -i 's/tini -s/tini -g/g' /opt/entrypoint.sh

WORKDIR $SPARK_HOME/work-dir
# Ensure that work-dir is writable by everyone
RUN chmod 0777 $SPARK_HOME/work-dir

ENTRYPOINT [ "/opt/entrypoint.sh" ]

USER jovyan
