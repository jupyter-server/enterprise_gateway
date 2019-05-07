FROM jupyter/minimal-notebook

ENV SPARK_VER 2.4.1
ENV SPARK_HOME /opt/spark
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

RUN conda install --quiet --yes \
    cffi \
    send2trash \
    requests \
    pycrypto && \
    conda clean -tipsy && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

USER root

RUN apt update && apt install -yq curl openjdk-8-jdk

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install /tmp/jupyter_enterprise_gateway*.whl && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway_kernelspecs*.tar.gz /usr/local/share/jupyter/kernels/
ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

COPY start-enterprise-gateway.sh bootstrap-enterprise-gateway.sh /usr/local/bin/

RUN chown jovyan:users /usr/local/bin/bootstrap-enterprise-gateway.sh && \
	chmod 0755 /usr/local/bin/bootstrap-enterprise-gateway.sh && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chown -R jovyan:users /usr/local/share/jupyter /usr/local/bin/kernel-launchers && \
	chmod 0666 /usr/local/share/jupyter/enterprise-gateway.log && \
	rm -f /usr/local/bin/bootstrap-kernel.sh

# Download and install Spark
RUN curl -s https://archive.apache.org/dist/spark/spark-${SPARK_VER}/spark-${SPARK_VER}-bin-hadoop2.7.tgz | \
    tar -xz -C /opt && \
    ln -s ${SPARK_HOME}-${SPARK_VER}-bin-hadoop2.7 $SPARK_HOME && \
    mkdir -p /usr/hdp/current && \
    ln -s ${SPARK_HOME}-${SPARK_VER}-bin-hadoop2.7 /usr/hdp/current/spark2-client

USER jovyan

ENTRYPOINT ["/usr/local/bin/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888

WORKDIR /usr/local/bin
