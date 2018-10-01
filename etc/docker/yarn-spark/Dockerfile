# Use docker image with Spark 2.1 and Hadoop 2.7 (sequenceiq/hadoop-docker:2.7.1)
FROM akchin/spark:2.3.1

ENV ANACONDA_HOME=/opt/anaconda2
ENV PATH=$ANACONDA_HOME/bin:$PATH
ENV PYSPARK_PYTHON=$ANACONDA_HOME/bin/python

COPY yarn-site.xml.template /usr/local/hadoop/etc/hadoop/

# Install system logging and insert into bootstrap.sh - helps in troubleshooting ssh
RUN cd /tmp && \
	curl -LO 'http://vault.centos.org/6.9/os/Source/SPackages/rsyslog-5.8.10-10.el6_6.src.rpm' && \
	rpm -i /tmp/rsyslog-5.8.10-10.el6_6.src.rpm && \
	rm -f /tmp/rsyslog-5.8.10-10.el6_6.src.rpm

# Update Java
RUN cd /tmp && \
	curl -LO 'http://download.oracle.com/otn-pub/java/jdk/8u181-b13/96a7b8442fe848ef90c96a2fad6ed6d1/jdk-8u181-linux-x64.rpm' -H 'Cookie: oraclelicense=accept-securebackup-cookie' && \
	rpm -e jdk-1.7.0_71-fcs.x86_64 && \
	rpm -i /tmp/jdk-8u181-linux-x64.rpm && \
	rm -f /tmp/jdk-8u181-linux-x64.rpm

# Install Anaconda
RUN cd /tmp && \
	curl -O https://repo.continuum.io/archive/Anaconda2-4.4.0-Linux-x86_64.sh && \
    bash /tmp/Anaconda2-4.4.0-Linux-x86_64.sh -b -p $ANACONDA_HOME && \
    rm -f /tmp/Anaconda2-4.4.0-Linux-x86_64.sh

# Install Toree
RUN cd /tmp && \
	curl -O https://dist.apache.org/repos/dist/release/incubator/toree/0.2.0-incubating/toree-pip/toree-0.2.0.tar.gz && \
	pip install --upgrade setuptools --user python && \
	pip install /tmp/toree-0.2.0.tar.gz && \
	jupyter toree install --spark_home=/usr/local/spark --kernel_name="Spark 2.3.1" --interpreters=Scala && \
	rm -f /tmp/toree-0.2.0.tar.gz

# Install Anaconda R binaries, argparser and kernelspecs dir
RUN conda install --yes --quiet -c r r-essentials r-irkernel && \
	Rscript -e 'install.packages("argparser", repos="https://cran.rstudio.com")' 

# Create service user 'elyra'. Pin uid/gid to 1111.
# Grant sudo privs to elyra. Unlock passwd (for ssh).
# Add users 'bob' and 'alice' for test/demo purposes.
# Add user 'jovyan' for compatibility with other Jupyter images.
RUN adduser elyra -u 1111 -G users && \
	echo "elyra ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/elyra && \
	chmod 0440 /etc/sudoers.d/elyra && \
	passwd -fu elyra && \
	adduser bob -u 1112 -G users && \
	adduser alice -u 1113 -G users && \
	adduser jovyan -u 1000 -G users

USER elyra

# passwordless ssh
RUN ssh-keygen -q -N "" -t rsa -f /home/elyra/.ssh/id_rsa && \
	cp /home/elyra/.ssh/id_rsa.pub /home/elyra/.ssh/authorized_keys && \
	chmod 0700 /home/elyra

USER root

ADD ssh_config /home/elyra/.ssh/config
RUN chmod 600 /home/elyra/.ssh/config && \
    chown elyra:elyra /home/elyra/.ssh/config

# install boot script
COPY bootstrap-yarn-spark.sh /etc/bootstrap-yarn-spark.sh
RUN chown root.root /etc/bootstrap-yarn-spark.sh && \
	chmod 0700 /etc/bootstrap-yarn-spark.sh

WORKDIR /usr/local/hadoop

ENTRYPOINT ["/etc/bootstrap-yarn-spark.sh"]
CMD ["--help"]

LABEL Hadoop.version="2.7.1"
LABEL Spark.version="2.3.1"
LABEL Anaconda.version="4.4.0"
LABEL Anaconda.python.version="2.7.13"
