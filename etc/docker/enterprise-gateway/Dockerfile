FROM elyra/spark-py:v2.4.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev curl krb5-dev

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install cffi send2trash /tmp/jupyter_enterprise_gateway*.whl && \
    pip install requests --upgrade && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway_kernelspecs*.tar.gz /usr/local/share/jupyter/kernels/
COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

COPY start-enterprise-gateway.sh bootstrap-enterprise-gateway.sh /usr/local/bin/

RUN adduser -S -u 1000 -G users jovyan && \
    chown jovyan:users /usr/local/bin/bootstrap-enterprise-gateway.sh && \
	chmod 0755 /usr/local/bin/bootstrap-enterprise-gateway.sh && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chown -R jovyan:users /usr/local/share/jupyter && \
	chmod 0666 /usr/local/share/jupyter/enterprise-gateway.log

USER jovyan

ENTRYPOINT ["/usr/local/bin/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888

WORKDIR /usr/local/bin
