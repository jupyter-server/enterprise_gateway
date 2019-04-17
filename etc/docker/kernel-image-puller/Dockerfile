FROM python:3

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY kernel_image_puller.py ./

# The following environment variables are supported - defaults provided.  Override as needed.
ENV KIP_GATEWAY_HOST http://localhost:8888
ENV KIP_INTERVAL 300
ENV KIP_LOG_LEVEL INFO
ENV KIP_NUM_PULLERS 2
ENV KIP_NUM_RETRIES 3
ENV KIP_PULL_POLICY 'IfNotPresent'

CMD [ "python", "./kernel_image_puller.py" ]
