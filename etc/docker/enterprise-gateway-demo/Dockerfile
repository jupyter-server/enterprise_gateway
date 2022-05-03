ARG HUB_ORG
ARG SPARK_VERSION

ARG BASE_CONTAINER=${HUB_ORG}/demo-base:${SPARK_VERSION}
FROM $BASE_CONTAINER

# An ARG declared before a FROM is outside of a build stage,
# so it can’t be used in any instruction after a FROM.
# To use the default value of an ARG declared before the first FROM
# use an ARG instruction without a value inside of a build stage:
ARG SPARK_VERSION

ENV NB_USER="jovyan"
ENV SPARK_VER=${SPARK_VERSION}

USER $NB_USER

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp/
RUN pip install /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway_kernelspecs*.tar.gz /usr/local/share/jupyter/kernels/

USER root
RUN fix-permissions /usr/local/share/jupyter/kernels/

COPY start-enterprise-gateway.sh.template /usr/local/bin/start-enterprise-gateway.sh
RUN chown $NB_USER: /usr/local/bin/start-enterprise-gateway.sh && \
    chmod +x /usr/local/bin/start-enterprise-gateway.sh

USER $NB_USER

# Massage kernelspecs to docker image env...
# Create symbolic link to preserve hdp-related directories
# Copy toree jar from install to scala kernelspec lib directory
# Add YARN_CONF_DIR to each env stanza, Add alternate-sigint to vanilla toree
RUN mkdir -p /tmp/byok/kernels && \
	cp /usr/local/share/jupyter/kernels/spark_${SPARK_VER}_scala/lib/*.jar /usr/local/share/jupyter/kernels/spark_scala_yarn_cluster/lib && \
	cp /usr/local/share/jupyter/kernels/spark_${SPARK_VER}_scala/lib/*.jar /usr/local/share/jupyter/kernels/spark_scala_yarn_client/lib && \
	cd /usr/local/share/jupyter/kernels && \
	for dir in spark_*; do cat $dir/kernel.json | sed s/'"env": {'/'"env": {|    "YARN_CONF_DIR": "\/usr\/hdp\/current\/hadoop\/etc\/hadoop",'/ | tr '|' '\n' > xkernel.json; mv xkernel.json $dir/kernel.json; done && \
	cat spark_${SPARK_VER}_scala/kernel.json | sed s/'"__TOREE_OPTS__": "",'/'"__TOREE_OPTS__": "--alternate-sigint USR2",'/ | tr '|' '\n' > xkernel.json; mv xkernel.json spark_${SPARK_VER}_scala/kernel.json && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chmod 0666 /usr/local/share/jupyter/enterprise-gateway.log

USER root

# install boot script
COPY bootstrap-enterprise-gateway.sh /usr/local/bin/bootstrap-enterprise-gateway.sh
RUN chown $NB_USER: /usr/local/bin/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /usr/local/bin/bootstrap-enterprise-gateway.sh

ENTRYPOINT ["/usr/local/bin/bootstrap-enterprise-gateway.sh"]
CMD ["--help"]

EXPOSE 8888

USER $NB_USER
