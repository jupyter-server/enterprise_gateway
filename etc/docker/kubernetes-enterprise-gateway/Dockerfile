FROM elyra/anaconda:dev

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install kubernetes && \
    pip install send2trash && \
    pip install jupyter_core==v4.4.0 && \
    pip install /tmp/jupyter_enterprise_gateway*.whl && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/
ADD start-enterprise-gateway.sh.template /usr/local/share/jupyter

# Create service user 'elyra'. Pin uid/gid to 1111.
RUN useradd elyra -m -u 1111 -G users

USER elyra

# passwordless ssh
RUN ssh-keygen -q -N "" -t rsa -f /home/elyra/.ssh/id_rsa && \
	cp /home/elyra/.ssh/id_rsa.pub /home/elyra/.ssh/authorized_keys && \
	chmod 0700 /home/elyra

USER root

ADD ssh_config /home/elyra/.ssh/config

RUN chmod 600 /home/elyra/.ssh/config && \
    chown elyra:elyra /home/elyra/.ssh/config

# install boot script
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh

RUN chown root.root /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /etc/bootstrap-enterprise-gateway.sh

ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888

WORKDIR /usr/local/share/jupyter

#USER elyra
