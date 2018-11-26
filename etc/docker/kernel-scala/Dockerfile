FROM elyra/spark:v2.4.0

COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

COPY bootstrap-kernel.sh /usr/local/bin/

RUN adduser -S -u 1000 -G users jovyan && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chown -R jovyan:users /usr/local/share/jupyter /opt/spark/work-dir

USER jovyan

