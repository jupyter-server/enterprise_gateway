FROM elyra/spark:v2.4.1

# Depending on the version of Kubernetes, some Spark jobs get
# failures attempting to create executors. These steps update
# the kubernetes client to 4.4.2 and will not be necessary
# once Spark 2.4.5 or 3.0 have been released.
# See https://issues.apache.org/jira/browse/SPARK-28921
RUN rm -f $SPARK_HOME/jars/kubernetes-*.jar
ADD https://repo1.maven.org/maven2/io/fabric8/kubernetes-client/4.4.2/kubernetes-client-4.4.2.jar $SPARK_HOME/jars
ADD https://repo1.maven.org/maven2/io/fabric8/kubernetes-model/4.4.2/kubernetes-model-4.4.2.jar $SPARK_HOME/jars
ADD https://repo1.maven.org/maven2/io/fabric8/kubernetes-model-common/4.4.2/kubernetes-model-common-4.4.2.jar $SPARK_HOME/jars

ADD jupyter_enterprise_gateway_kernel_image_files*.tar.gz /usr/local/bin/

RUN adduser -S -u 1000 -G users jovyan && \
    chown jovyan:users /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0755 /usr/local/bin/bootstrap-kernel.sh && \
	chmod 0777 /opt/spark/work-dir && \
    chown -R jovyan:users /usr/local/bin/kernel-launchers

USER jovyan
ENV KERNEL_LANGUAGE scala
CMD /usr/local/bin/bootstrap-kernel.sh
