ARG BASE_CONTAINER=python:3.10-bookworm
FROM $BASE_CONTAINER

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY kernel_image_puller.py ./
COPY image_fetcher.py ./
ARG OS=Debian_12

# Install crictl for use by KIP when non-docker installations are encountered.
RUN mkdir -p /etc/apt/keyrings && \
    curl -L https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/$OS/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubic.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/kubic.gpg] https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/${OS}/ /" > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list && \
    apt-get update && apt-get install -y cri-tools

RUN echo $PATH
# The following environment variables are supported - defaults provided.  Override as needed.
ENV KIP_GATEWAY_HOST http://localhost:8888
ENV KIP_INTERVAL 300
ENV KIP_LOG_LEVEL INFO
ENV KIP_NUM_PULLERS 2
ENV KIP_NUM_RETRIES 3
ENV KIP_PULL_POLICY 'IfNotPresent'

CMD [ "python", "./kernel_image_puller.py" ]
