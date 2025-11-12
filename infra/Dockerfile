FROM elyra/enterprise-gateway:3.2.3

# FROM elyra/enterprise-gateway:2.2.6

USER root

RUN groupadd -g 1000 jovyan || true && \
    useradd -u 1000 -g 1000 -m -s /bin/bash jovyan || true

RUN mkdir -p /home/jovyan/.ssh && \
    chown -R jovyan:jovyan /home/jovyan/.ssh && \
    chmod 700 /home/jovyan/.ssh

COPY --chown=jovyan:jovyan ssh_keys/id_rsa /home/jovyan/.ssh/id_rsa

RUN chmod 600 /home/jovyan/.ssh/id_rsa

RUN apt-get update && \
    apt-get install -y openssh-client curl netcat-openbsd sshpass && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade docker paramiko cryptography

# Copy JEG source code
COPY ../jeg /opt/jeg

RUN rm -rf /usr/local/share/jupyter/enterprise_gateway && \
    cp -r /opt/JEGgernaut/enterprise_gateway /usr/local/share/jupyter/

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

COPY jeg_config.py /etc/jupyter/jeg_config.py

RUN chmod +x /usr/local/bin/entrypoint.sh

ENV JUPYTER_CONFIG_DIR=/etc/jupyter
ENV PYTHONUNBUFFERED=1

WORKDIR /home/jovyan

EXPOSE 8888 8889 8877

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]