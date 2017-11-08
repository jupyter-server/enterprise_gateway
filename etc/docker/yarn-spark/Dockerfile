# Use docker image with Spark 2.1 and Hadoop 2.7 (sequenceiq/hadoop-docker:2.7.1)
FROM aghorbani/spark:2.1.0

ENV ANACONDA_HOME=/opt/anaconda2
ENV PATH=$ANACONDA_HOME/bin:$PATH
ENV PYSPARK_PYTHON=$ANACONDA_HOME/bin/python

# Install system logging and insert into bootstrap.sh - helps in troubleshooting ssh
RUN cd /tmp && \
	curl -LO 'http://vault.centos.org/6.9/os/Source/SPackages/rsyslog-5.8.10-10.el6_6.src.rpm' && \
	rpm -i /tmp/rsyslog-5.8.10-10.el6_6.src.rpm && \
	rm -f /tmp/rsyslog-5.8.10-10.el6_6.src.rpm && \
	RUN cat /etc/bootstrap.sh | sed s/'service sshd'/'service rsyslog start|service sshd'/ | tr '|' '\n' > /tmp/bootstrap.sh && \
	mv /tmp/bootstrap.sh /etc && \
	chmod 700 /etc/bootstrap.sh

# Update Java
RUN cd /tmp && \
	curl -LO 'http://download.oracle.com/otn-pub/java/jdk/8u151-b12/e758a0de34e24606bca991d704f6dcbf/jdk-8u151-linux-x64.rpm' -H 'Cookie: oraclelicense=accept-securebackup-cookie' && \
	rpm -e jdk-1.7.0_71-fcs.x86_64 && \
	rpm -i /tmp/jdk-8u151-linux-x64.rpm && \
	rm -f /tmp/jdk-8u151-linux-x64.rpm


# Install Anaconda
RUN cd /tmp && \
	curl -O https://repo.continuum.io/archive/Anaconda2-4.4.0-Linux-x86_64.sh && \
    bash /tmp/Anaconda2-4.4.0-Linux-x86_64.sh -b -p $ANACONDA_HOME && \
    rm -f /tmp/Anaconda2-4.4.0-Linux-x86_64.sh

# Install Toree
RUN cd /tmp && \
	curl -O https://dist.apache.org/repos/dist/dev/incubator/toree/0.2.0-incubating-rc1/toree-pip/toree-0.2.0.tar.gz && \
	pip install /tmp/toree-0.2.0.tar.gz && \
	jupyter toree install --spark_home=/usr/local/spark --kernel_name="Spark 2.1" --interpreters=Scala && \
	rm -f /tmp/toree-0.2.0.tar.gz

# Install Anaconda R binaries, argparser and kernelspecs dir
RUN conda install --yes --quiet -c r r-essentials r-irkernel && \
	Rscript -e 'install.packages("argparser", repos="https://cran.rstudio.com")' 

LABEL Hadoop.version="2.7.1"
LABEL Spark.version="2.1.0"
LABEL Anaconda.version="4.4.0"
LABEL Anaconda.python.version="2.7.13"
