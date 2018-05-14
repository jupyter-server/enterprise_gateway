FROM kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0

RUN apk add --no-cache build-base libffi-dev openssl-dev python-dev && \
    pip install cffi ipykernel ipython jupyter_client

ADD jupyter_enterprise_gateway*.tar.gz /usr/local/share/jupyter/kernels/

COPY bootstrap-kernel.sh /etc

# FIXME Set the extra classpath option.  This will work around an issue that has
# been fixed in the Spark-on-kubernetes repo, but not persisted in their
# images yet. https://github.com/apache-spark-on-k8s/spark/pull/541
ENV SPARK_SUBMIT_EXTRA_CLASSPATH=/opt/spark/spark-examples.jar
