FROM elyra/anaconda:dev

# install boot script

COPY bootstrap-kernel.sh /etc/bootstrap-kernel.sh

# install kernel support scripts

RUN mkdir -p /opt/elyra/bin && \
    mkdir -p /opt/elyra/conf

COPY launch_ipykernel.py /opt/elyra/bin/launch_ipykernel.py

RUN chown root.root /etc/bootstrap-kernel.sh && \
	chmod 0700 /etc/bootstrap-kernel.sh && \
	chown -R root.root /opt/elyra && \
	chmod 0700 /opt/elyra/bin/launch_ipykernel.py

WORKDIR /usr/local/share/jupyter 

ENTRYPOINT ["/etc/bootstrap-kernel.sh"]
