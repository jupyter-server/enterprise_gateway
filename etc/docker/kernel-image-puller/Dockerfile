ARG BASE_CONTAINER=python:3
FROM $BASE_CONTAINER

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY kernel_image_puller.py ./

# Install crictl for use by KIP when non-docker installations are encountered.
ARG CRICTL_VERSION=v1.22.0
RUN curl -sL https://github.com/kubernetes-sigs/cri-tools/releases/download/${CRICTL_VERSION}/crictl-${CRICTL_VERSION}-linux-amd64.tar.gz | tar zxv -C /usr/local/bin

RUN echo $PATH
# The following environment variables are supported - defaults provided.  Override as needed.
ENV KIP_GATEWAY_HOST http://localhost:8888
ENV KIP_INTERVAL 300
ENV KIP_LOG_LEVEL INFO
ENV KIP_NUM_PULLERS 2
ENV KIP_NUM_RETRIES 3
ENV KIP_PULL_POLICY 'IfNotPresent'

CMD [ "python", "./kernel_image_puller.py" ]
