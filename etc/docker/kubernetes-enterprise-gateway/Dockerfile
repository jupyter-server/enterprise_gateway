FROM kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install cffi &&\
    pip install kubernetes && \
    pip install send2trash && \
    pip install jupyter_core==v4.4.0 && \
    pip install /tmp/jupyter_enterprise_gateway*.whl && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/
COPY start-enterprise-gateway.sh.template /usr/local/share/jupyter
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh

RUN chown root.root /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /etc/bootstrap-enterprise-gateway.sh && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chmod 0777 /usr/local/share/jupyter/enterprise-gateway.log


ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888

WORKDIR /usr/local/share/jupyter
