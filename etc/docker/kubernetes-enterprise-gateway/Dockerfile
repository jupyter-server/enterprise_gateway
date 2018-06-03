FROM kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev curl

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install cffi kubernetes send2trash /tmp/jupyter_enterprise_gateway*.whl && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

# Install Toree for both vanilla and cluster - although these are not used except for runtime discovery.
RUN cd /tmp && \
	curl -O https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0-incubating-rc5/toree-pip/toree-0.2.0.tar.gz && \
	tar xf toree-0.2.0.tar.gz && \
	cp toree-0.2.0/toree/lib/toree-assembly-0.2.0-incubating.jar /usr/local/share/jupyter/kernels/scala_kubernetes/lib && \
	cp toree-0.2.0/toree/lib/toree-assembly-0.2.0-incubating.jar /usr/local/share/jupyter/kernels/spark_scala_kubernetes/lib && \
	rm -rf toree-0.2.0*

COPY start-enterprise-gateway.sh.template /usr/local/share/jupyter
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh

RUN chown root.root /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /etc/bootstrap-enterprise-gateway.sh && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chmod 0777 /usr/local/share/jupyter/enterprise-gateway.log


ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888

WORKDIR /usr/local/share/jupyter
