FROM tensorflow/tensorflow:1.6.0-py3

#RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
#    pip install cffi 

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY *.sh /etc/

