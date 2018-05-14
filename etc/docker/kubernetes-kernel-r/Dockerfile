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
        -e "install.packages(pkgs=c('argparser','jsonlite','uuid','stringr','repr','IRdisplay','evaluate', 'crayon', 'pbdZMQ', 'devtools', 'digest'), \
        lib='/usr/lib/R/library', repos=c('http://cran.cnr.berkeley.edu/'))" \
        -e "devtools::install_github('IRkernel/IRkernel')"

# Install OOTB kernelspecs
ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY bootstrap-kernel.sh /etc

ENV R_LIBS_USER ${R_HOME}/library:${SPARK_HOME}/R/lib

# FIXME Set the extra classpath option.  This will work around an issue that has
# been fixed in the Spark-on-kubernetes repo, but not persisted in their
# images yet. https://github.com/apache-spark-on-k8s/spark/pull/541
ENV SPARK_SUBMIT_EXTRA_CLASSPATH=/opt/spark/spark-examples.jar
