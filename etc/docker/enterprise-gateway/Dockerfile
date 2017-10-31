FROM elyra/hadoop-spark:2.7.1-2.1.0

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install /tmp/jupyter_enterprise_gateway*.whl && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/
ADD start-enterprise-gateway.sh.template /usr/local/share/jupyter

# Massage kernelspecs to docker image env...
# Create symbolic link to preserve hdp-related directories
# Copy toree jar from install to scala kernelspec lib directory
# Add YARN_CONF_DIR to each env stanza, Add PATH to R-yarn-client env stanza
RUN mkdir -p /usr/hdp/current && \
	ln -s /usr/local/spark-2.1.0-bin-hadoop2.7 /usr/hdp/current/spark2-client && \
	cp /usr/local/share/jupyter/kernels/spark_2.1_scala/lib/*.jar /usr/local/share/jupyter/kernels/spark_2.1_scala_yarn_cluster/lib && \
	cp /usr/local/share/jupyter/kernels/spark_2.1_scala/lib/*.jar /usr/local/share/jupyter/kernels/spark_2.1_scala_yarn_client/lib && \
	cd /usr/local/share/jupyter/kernels && \
	for dir in spark_2.1_*; do cat $dir/kernel.json | sed s/'"env": {'/'"env": {|    "YARN_CONF_DIR": "\/usr\/local\/hadoop\/etc\/hadoop",'/ | tr '|' '\n' > xkernel.json; mv xkernel.json $dir/kernel.json; done && \
	cat spark_2.1_R_yarn_client/kernel.json | sed s/'"env": {'/'"env": {|    "PATH": "\/opt\/anaconda2\/bin:$PATH",'/ | tr '|' '\n' > xkernel.json; mv xkernel.json spark_2.1_R_yarn_client/kernel.json && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chmod 0666 /usr/local/share/jupyter/enterprise-gateway.log

# Create service user 'elyra'. Pin uid/gid to 1111.  
# Grant sudo privs to elyra. Unlock passwd (for ssh).
# Add users 'bob' and 'alice' for test/demo purposes.
# Add user 'jovyan' for compatibility with other Jupyter images.
RUN adduser elyra -u 1111 -G users && \
	echo "elyra ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/elyra && \
	chmod 0440 /etc/sudoers.d/elyra && \
	passwd -fu elyra && \
	adduser bob -u 1112 -G users && \
	adduser alice -u 1113 -G users && \
	adduser jovyan -u 1000 -G users 

USER elyra

# passwordless ssh
RUN ssh-keygen -q -N "" -t rsa -f /home/elyra/.ssh/id_rsa && \
	cp /home/elyra/.ssh/id_rsa.pub /home/elyra/.ssh/authorized_keys && \
	chmod 0700 /home/elyra

USER root

# install boot script 
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh
RUN chown root.root /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /etc/bootstrap-enterprise-gateway.sh

WORKDIR /usr/local/share/jupyter 

ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888
