FROM elyra/spark:v2.4.0

COPY kernel-launchers /usr/local/share/jupyter/kernel-launchers/

COPY bootstrap-kernel.sh /etc/

RUN addgroup -S -g 620 eg-kernel && adduser -S -u 620 -G eg-kernel eg-kernel && \
    chown eg-kernel.eg-kernel /etc/bootstrap-kernel.sh && \
	chmod 0755 /etc/bootstrap-kernel.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter /opt/spark/work-dir

USER eg-kernel
