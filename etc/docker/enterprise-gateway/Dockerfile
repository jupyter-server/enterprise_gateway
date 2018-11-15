FROM elyra/spark-py:v2.4.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev curl krb5-dev

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install cffi send2trash /tmp/jupyter_enterprise_gateway*.whl && \
    pip install requests --upgrade && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway_kernelspecs*.tar.gz /usr/local/share/jupyter/kernels/

COPY start-enterprise-gateway.sh /usr/local/share/jupyter
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh

RUN addgroup -S -g 619 eg-svc && adduser -S -u 619 -G eg-svc eg-svc && \
    chown eg-svc.eg-svc /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0755 /etc/bootstrap-enterprise-gateway.sh && \
	touch /usr/local/share/jupyter/enterprise-gateway.log && \
	chown -R eg-svc.eg-svc /usr/local/share/jupyter && \
	chmod 0666 /usr/local/share/jupyter/enterprise-gateway.log

USER eg-svc

ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888

WORKDIR /usr/local/share/jupyter
