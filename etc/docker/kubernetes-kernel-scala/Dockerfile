FROM kubespark/spark-driver:v2.2.0-kubernetes-0.5.0

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

# Install Toree for both vanilla and cluster
RUN cd /tmp && \
    apk --no-cache add curl && \
	curl -O https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0-incubating-rc5/toree-pip/toree-0.2.0.tar.gz && \
	tar xf toree-0.2.0.tar.gz && \
	cp toree-0.2.0/toree/lib/toree-assembly-0.2.0-incubating.jar /usr/local/share/jupyter/kernels/scala_kubernetes/lib && \
	cp toree-0.2.0/toree/lib/toree-assembly-0.2.0-incubating.jar /usr/local/share/jupyter/kernels/spark_scala_kubernetes/lib && \
	rm -rf toree-0.2.0*

COPY bootstrap-kernel.sh spark-exec.sh /etc/

RUN addgroup -S -g 620 eg-kernel && adduser -S -u 620 -G eg-kernel eg-kernel && \
    chown eg-kernel.eg-kernel /etc/bootstrap-kernel.sh /etc/spark-exec.sh && \
	chmod 0755 /etc/bootstrap-kernel.sh /etc/spark-exec.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter /opt/spark/work-dir

USER eg-kernel

CMD /etc/spark-exec.sh
