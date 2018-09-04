FROM kubespark/spark-driver-r:v2.2.0-kubernetes-0.5.0

# Install items necessary for IRKernel and launcher to run.
# First some python things...
RUN apk add --no-cache build-base libzmq openssl-dev python-dev && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools jupyter_client && \
    rm -r /root/.cache

# then some R things...
RUN mkdir -p /usr/share/doc/R/html && \
    Rscript --slave --no-save --no-restore-history \
        -e "install.packages(pkgs=c('argparser','jsonlite','uuid','stringr','repr','IRdisplay','evaluate', 'crayon', 'pbdZMQ', 'devtools', 'digest', 'base64enc'), \
        lib='/usr/lib/R/library', repos=c('http://cran.cnr.berkeley.edu/'))" \
        -e "devtools::install_github('IRkernel/IRkernel')"

# Install OOTB kernelspecs
ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY spark-exec.sh /etc/

RUN addgroup -S -g 620 eg-kernel && adduser -S -u 620 -G eg-kernel eg-kernel && \
    chown eg-kernel.eg-kernel /etc/spark-exec.sh && \
	chmod 0755 /etc/spark-exec.sh && \
	chown -R eg-kernel.eg-kernel /usr/local/share/jupyter /opt/spark/work-dir

USER eg-kernel

ENV R_LIBS_USER ${R_HOME}/library:${SPARK_HOME}/R/lib

CMD /etc/spark-exec.sh
