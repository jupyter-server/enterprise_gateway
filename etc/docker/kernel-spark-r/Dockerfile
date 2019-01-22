FROM elyra/spark-r:v3.0.0.4c1cd80

# Install items necessary for IRKernel and launcher to run.
# First some python things...
RUN apk add --no-cache build-base libzmq python-dev && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools jupyter_client && \
    rm -r /root/.cache

# then some R things...
RUN mkdir -p /usr/share/doc/R/html && \
    Rscript --slave --no-save --no-restore-history \
        -e "install.packages(pkgs=c('argparse','jsonlite','uuid','stringr','repr','IRkernel','IRdisplay', \
                                    'evaluate', 'crayon', 'pbdZMQ', 'digest', 'base64enc','versions'), \
                                    lib='/usr/lib/R/library', repos=c('http://cran.cnr.berkeley.edu/'))" \
        -e "versions::install.versions('devtools', '1.13.6', lib='/usr/lib/R/library')"

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin

RUN adduser -S -u 1000 -G users jovyan && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers /opt/spark/work-dir

USER jovyan

ENV KERNEL_LANGUAGE=R R_LIBS_USER=${R_HOME}/library:${SPARK_HOME}/R/lib
