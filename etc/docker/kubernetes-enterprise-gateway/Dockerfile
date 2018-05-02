FROM elyra/anaconda:dev

# Install Enterprise Gateway wheel and kernelspecs
COPY jupyter_enterprise_gateway*.whl /tmp
RUN pip install kubernetes && \
    pip install send2trash && \
    pip install /tmp/jupyter_enterprise_gateway*.whl && \
	rm -f /tmp/jupyter_enterprise_gateway*.whl

# Create service user 'elyra'. Pin uid/gid to 1111.
# Grant sudo privs to elyra. Unlock passwd (for ssh).
# Add users 'bob' and 'alice' for test/demo purposes.
# Add user 'jovyan' for compatibility with other Jupyter images.
RUN adduser elyra -u 1111 --ingroup users && \
	echo "elyra ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/elyra && \
	chmod 0440 /etc/sudoers.d/elyra && \
	passwd -fu elyra && \
	adduser bob -u 1112 --ingroup users && \
	adduser alice -u 1113 --ingroup users && \
	adduser jovyan -u 1000 --ingroup users

USER elyra

# passwordless ssh
RUN ssh-keygen -q -N "" -t rsa -f /home/elyra/.ssh/id_rsa && \
	cp /home/elyra/.ssh/id_rsa.pub /home/elyra/.ssh/authorized_keys && \
	chmod 0700 /home/elyra

COPY ~/.kube /home/elyra/.kube/

USER root

ADD ssh_config /home/elyra/.ssh/config
RUN chmod 600 /home/elyra/.ssh/config && \
    chown elyra:elyra /home/elyra/.ssh/config

# install boot script
COPY bootstrap-enterprise-gateway.sh /etc/bootstrap-enterprise-gateway.sh
RUN chown root.root /etc/bootstrap-enterprise-gateway.sh && \
	chmod 0700 /etc/bootstrap-enterprise-gateway.sh

WORKDIR /usr/local/share/jupyter

ENTRYPOINT ["/etc/bootstrap-enterprise-gateway.sh"]

EXPOSE 8888
