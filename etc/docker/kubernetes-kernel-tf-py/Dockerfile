FROM tensorflow/tensorflow:1.8.0-py3

RUN pip install pycrypto

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY *.sh /etc/

