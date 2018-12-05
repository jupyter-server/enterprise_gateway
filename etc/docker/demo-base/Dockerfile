FROM centos:7

MAINTAINER akchinSTC

# INSTALL / DOWNLOAD ALL NEEDED PACKAGES
RUN yum update -y && \
    yum install -y which tar bzip2 wget curl sudo openssh-server openssh-clients java-1.8.0-openjdk.x86_64 less \
                   unzip gcc krb5-devel file libunwind && \
    yum clean all

# SYSTEM ENVS
ENV JAVA_HOME /usr/lib/jvm/jre-1.8.0
ENV PATH $PATH:$JAVA_HOME/bin
ENV ANACONDA_HOME=/opt/anaconda2/

# SPARK ENVS
ENV SPARK_VER 2.4.0
ENV SPARK_HOME /usr/local/spark
ENV PYSPARK_PYTHON=$ANACONDA_HOME/bin/python

# HADOOP ENVS
ENV HADOOP_VER 2.7.7
ENV HADOOP_PREFIX /usr/local/hadoop
ENV HADOOP_CONF_DIR $HADOOP_PREFIX/etc/hadoop

ENV PATH=$ANACONDA_HOME/bin:$HADOOP_PREFIX/bin:$SPARK_HOME/bin:$PATH

# DOWNLOAD HADOOP AND SPARK
RUN curl -s http://www.eu.apache.org/dist/hadoop/common/hadoop-$HADOOP_VER/hadoop-$HADOOP_VER.tar.gz | tar -xz -C /usr/local
RUN mkdir -p /tmp/native && curl -Ls http://dl.bintray.com/sequenceiq/sequenceiq-bin/hadoop-native-64-2.7.0.tar | tar -x -C /tmp/native
RUN curl -s http://apache.cs.utah.edu/spark/spark-${SPARK_VER}/spark-${SPARK_VER}-bin-hadoop2.7.tgz | tar -xz -C /usr/local

# INSTALL MINI-CONDA AND PYTHON PACKAGES
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda2-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p $ANACONDA_HOME && \
    rm ~/miniconda.sh && \
    ln -s /opt/anaconda2/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/anaconda2/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc
RUN conda install -v --yes --quiet pip jupyter r-devtools r-stringr
RUN Rscript -e 'install.packages("argparser", repos="http://cran.cnr.berkeley.edu")' \
	        -e 'install.packages("IRkernel", repos="http://cran.cnr.berkeley.edu", lib="/opt/anaconda2/lib/R/library")' \
	        -e 'IRkernel::installspec(prefix = "/usr/local")' \
            -e 'devtools::install_github("apache/spark@v$SPARK_VER", subdir="R/pkg")'

# SETUP HADOOP CONFIGS
RUN cd /usr/local && ln -s ./hadoop-$HADOOP_VER hadoop
RUN sed -i '/^export JAVA_HOME/ s:.*:export JAVA_HOME=/usr/lib/jvm/jre-1.8.0\nexport HADOOP_PREFIX=/usr/local/hadoop\nexport HADOOP_HOME=/usr/local/hadoop\n:' $HADOOP_PREFIX/etc/hadoop/hadoop-env.sh
RUN sed -i '/^export HADOOP_CONF_DIR/ s:.*:export HADOOP_CONF_DIR=/usr/local/hadoop/etc/hadoop/:' $HADOOP_PREFIX/etc/hadoop/hadoop-env.sh
# SETUP PSEUDO - DISTRIBUTED CONFIGS FOR HADOOP
COPY ["core-site.xml.template", "hdfs-site.xml", "mapred-site.xml", "yarn-site.xml.template", \
      "$HADOOP_PREFIX/etc/hadoop/"]
RUN sed s/HOSTNAME/localhost/ /usr/local/hadoop/etc/hadoop/core-site.xml.template > /usr/local/hadoop/etc/hadoop/core-site.xml

# working around docker.io build error
RUN ls -la /usr/local/hadoop/etc/hadoop/*-env.sh && \
    chmod +x /usr/local/hadoop/etc/hadoop/*-env.sh && \
    ls -la /usr/local/hadoop/etc/hadoop/*-env.sh

# SETUP SPARK CONFIGS
RUN cd /usr/local && \
    ln -s spark-${SPARK_VER}-bin-hadoop2.7 spark

# Install Toree
RUN cd /tmp && \
	curl -O https://dist.apache.org/repos/dist/release/incubator/toree/0.3.0-incubating/toree-pip/toree-0.3.0.tar.gz && \
	pip install --upgrade setuptools --user python && \
	pip install /tmp/toree-0.3.0.tar.gz && \
	jupyter toree install --spark_home=/usr/local/spark --kernel_name="Spark 2.4.0" --interpreters=Scala && \
	rm -f /tmp/toree-0.3.0.tar.gz

# SETUP HADOOP NATIVE SUPPORT - not sure if this works with 2.7.7
# using recompiled 64 libs from SequenceIQ
RUN rm -rf $HADOOP_PREFIX/lib/native && mv /tmp/native $HADOOP_PREFIX/lib

# SETUP PASSWORDLESS SSH
RUN ssh-keygen -q -N "" -t dsa -f /etc/ssh/ssh_host_dsa_key && \
    ssh-keygen -q -N "" -t rsa -f /etc/ssh/ssh_host_rsa_key && \
    ssh-keygen -q -N "" -t rsa -f /root/.ssh/id_rsa && \
    cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys
RUN ssh-keygen -A
COPY ssh_config /root/.ssh/config
RUN chmod 600 /root/.ssh/config && \
    chown root:root /root/.ssh/config && \
    echo "Port 2122" >> /etc/ssh/sshd_config
RUN pkill sshd; /usr/sbin/sshd

# Create service user 'jovyan'. Pin uid/gid to 1000.
# Grant sudo privs to jovyan. Unlock passwd (for ssh).
# Add users 'bob' and 'alice' and 'elyra' for test/demo purposes.
RUN adduser jovyan -u 1000 -G users && \
	echo "jovyan ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/jovyan && \
	chmod 0440 /etc/sudoers.d/jovyan && \
	passwd -fu jovyan && \
	adduser bob -u 1112 -G users && \
	adduser alice -u 1113 -G users && \
	adduser elyra -u 1111 -G users

USER jovyan

# SETUP PASSWORDLESS SSH FOR JOVYAN
RUN ssh-keygen -q -N "" -t rsa -f /home/jovyan/.ssh/id_rsa && \
	cp /home/jovyan/.ssh/id_rsa.pub /home/jovyan/.ssh/authorized_keys && \
	chmod 0700 /home/jovyan

USER root

COPY ssh_config /home/jovyan/.ssh/config
RUN chmod 600 /home/jovyan/.ssh/config && \
    chown jovyan: /home/jovyan/.ssh/config

COPY bootstrap-yarn-spark.sh /usr/local/bin/
RUN chown root.root /usr/local/bin/bootstrap-yarn-spark.sh && \
	chmod 0700 /usr/local/bin/bootstrap-yarn-spark.sh

CMD /usr/local/bin/bootstrap-yarn-spark.sh

LABEL Hadoop.version=$HADOOP_VER
LABEL Spark.version=$SPARK_VER

# Hdfs ports
EXPOSE 50010 50020 50070 50075 50090 8020 9000 \
# Mapred ports
19888 \
#Yarn ports
8030 8031 8032 8033 8040 8042 8088 \
#Other ports
49707 2122