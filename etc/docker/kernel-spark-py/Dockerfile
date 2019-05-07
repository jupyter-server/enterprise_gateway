ARG HUB_ORG
ARG TAG

# Ubuntu 18.04.1 LTS Bionic
FROM $HUB_ORG/kernel-py:$TAG

ENV SPARK_VER 2.4.1
ENV SPARK_HOME /opt/spark
ENV KERNEL_LANGUAGE python
ENV R_LIBS_USER $R_LIBS_USER:${SPARK_HOME}/R/lib
ENV PATH $PATH:$SPARK_HOME/bin

USER root

RUN apt-get update && \
    apt-get install -yq --no-install-recommends \
    openjdk-8-jdk \
    less \
    curl \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME /usr/lib/jvm/java-1.8.0-openjdk-amd64

# Download and install Spark
RUN curl -s https://archive.apache.org/dist/spark/spark-${SPARK_VER}/spark-${SPARK_VER}-bin-hadoop2.7.tgz | \
    tar -xz -C /opt && \
    ln -s ${SPARK_HOME}-${SPARK_VER}-bin-hadoop2.7 $SPARK_HOME

# Download entrypoint.sh from matching tag
# Use tini from Anaconda installation
RUN cd /opt/ && \
    wget https://raw.githubusercontent.com/apache/spark/v${SPARK_VER}/resource-managers/kubernetes/docker/src/main/dockerfiles/spark/entrypoint.sh && \
    chmod a+x /opt/entrypoint.sh && \
    sed -i 's/tini -s/tini -g/g' /opt/entrypoint.sh && \
    ln -sfn /opt/conda/bin/tini /sbin/tini

WORKDIR $SPARK_HOME/work-dir
# Ensure that work-dir is writable by everyone
RUN chmod 0777 $SPARK_HOME/work-dir

ENTRYPOINT [ "/opt/entrypoint.sh" ]

USER jovyan


