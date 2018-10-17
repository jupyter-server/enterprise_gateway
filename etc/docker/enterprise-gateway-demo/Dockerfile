FROM elyra/yarn-spark:dev

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp

RUN pip install /tmp/jupyter_enterprise_gateway*.whl && \
    pip install --upgrade ipykernel jupyter-client notebook && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway_kernelspecs*.tar.gz /usr/local/share/jupyter/kernels/
COPY start-enterprise-gateway.sh.template /usr/local/share/jupyter/

# Massage kernelspecs to docker image env...
# Create symbolic link to preserve hdp-related directories
# Copy toree jar from install to scala kernelspec lib directory
# Add YARN_CONF_DIR to each env stanza, Add alternate-sigint to vanilla toree
RUN mkdir -p /usr/hdp/current /tmp/byok/kernels && \
	ln -s /usr/local/spark-2.3.1-bin-hadoop2.7 /usr/hdp/current/spark2-client && \
	cp /usr/local/share/jupyter/kernels/spark_2.3.1_scala/lib/*.jar /usr/local/share/jupyter/kernels/spark_scala_yarn_cluster/lib && \
	cp /usr/local/share/jupyter/kernels/spark_2.3.1_scala/lib/*.jar /usr/local/share/jupyter/kernels/spark_scala_yarn_client/lib && \
	cd /usr/local/share/jupyter/kernels && \
	for dir in spark_*; do cat $dir/kernel.json | sed s/'"env": {'/'"env": {|    "YARN_CONF_DIR": "\/usr\/local\/hadoop\/etc\/hadoop",'/ | tr '|' '\n' > xkernel.json; mv xkernel.json $dir/kernel.json; done && \
	cat spark_2.3.1_scala/kernel.json | sed s/'"__TOREE_OPTS__": "",'/'"__TOREE_OPTS__": "--alternate-sigint USR2",'/ | tr '|' '\n' > xkernel.json; mv xkernel.json spark_2.3.1_scala/kernel.json && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chmod 0666 /usr/local/share/jupyter/enterprise-gateway.log

# install boot script 
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh
RUN chown root.root /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /etc/bootstrap-enterprise-gateway.sh

WORKDIR /usr/local/share/jupyter 

ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]
CMD ["--help"]

EXPOSE 8888
