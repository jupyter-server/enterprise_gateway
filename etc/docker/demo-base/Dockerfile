ARG BASE_CONTAINER=continuumio/miniconda3
FROM $BASE_CONTAINER

ARG SPARK_VERSION
ARG SPARKR_VERSION=3.1.2
ARG NB_USER="jovyan"
ARG NB_UID="1000"
ARG NB_GID="100"

USER root

ENV HADOOP_HOME=/usr/hdp/current/hadoop \
    ANACONDA_HOME=/opt/conda

ENV SHELL=/bin/bash \
    NB_USER=$NB_USER \
    NB_UID=$NB_UID \
    NB_GID=$NB_GID \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    JAVA_HOME=/usr/lib/jvm/java \
    SPARK_HOME=/usr/hdp/current/spark2-client \
    PYSPARK_PYTHON=$ANACONDA_HOME/bin/python \
    HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop

ENV HOME=/home/$NB_USER \
    PATH=$JAVA_HOME/bin:$ANACONDA_HOME/bin:$HADOOP_HOME/bin:$SPARK_HOME/bin:$PATH

ENV SPARK_VER $SPARK_VERSION
ENV HADOOP_VER 3.3.1

# INSTALL / DOWNLOAD ALL NEEDED PACKAGES
RUN dpkg --purge --force-depends ca-certificates-java \
    && apt-get update && apt-get -yq dist-upgrade \
    && apt-get install -yq --no-install-recommends \
    wget \
    bzip2 \
    tar \
    curl \
    less \
    nano \
    ca-certificates \
    libkrb5-dev \
    sudo \
    locales \
    gcc \
    fonts-liberation \
    unzip \
    libsm6 \
    libxext-dev \
    libxrender1 \
    software-properties-common \
    openssh-server \
    openssh-client \
    && apt-add-repository 'deb http://security.debian.org/debian-security bullseye-security main' \
    && apt-add-repository 'deb http://deb.debian.org/debian/ sid main' \
    && apt-get update && apt-get install -yq --no-install-recommends  \
    openjdk-8-jre-headless \
    ca-certificates-java \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s $(readlink -f /usr/bin/javac | sed "s:/bin/javac::") ${JAVA_HOME}

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

ADD fix-permissions /usr/local/bin/fix-permissions
# Create jovyan user with UID=1000 and in the 'users' group
# and make sure these dirs are writable by the `users` group.
RUN groupadd wheel -g 11 && \
    echo "auth required pam_wheel.so use_uid" >> /etc/pam.d/su && \
    useradd -m -s /bin/bash -N -u $NB_UID $NB_USER && \
    mkdir -p /usr/hdp/current && \
    mkdir -p /usr/local/share/jupyter && \
    chown $NB_USER:$NB_GID $ANACONDA_HOME && \
    chmod g+w /etc/passwd && \
    chmod +x /usr/local/bin/fix-permissions && \
    fix-permissions $HOME && \
    fix-permissions $ANACONDA_HOME && \
    fix-permissions /usr/hdp/current && \
    fix-permissions /usr/local/share/jupyter

# Create service user 'jovyan'. Pin uid/gid to 1000.
RUN useradd -m -s /bin/bash -N -u 1111 elyra && \
    useradd -m -s /bin/bash -N -u 1112 bob  && \
    useradd -m -s /bin/bash -N -u 1113 alice

USER $NB_UID

# Setup work directory for backward-compatibility
RUN mkdir /home/$NB_USER/work && \
    fix-permissions /home/$NB_USER

# DOWNLOAD HADOOP AND SPARK
RUN curl -sL https://archive.apache.org/dist/hadoop/common/hadoop-$HADOOP_VER/hadoop-$HADOOP_VER.tar.gz | tar -xz -C /usr/hdp/current
RUN curl -sL https://archive.apache.org/dist/spark/spark-$SPARK_VER/spark-$SPARK_VER-bin-hadoop3.2.tgz | tar -xz -C /usr/hdp/current
# SETUP SPARK AND HADOOP SYMLINKS
RUN cd /usr/hdp/current && ln -s ./hadoop-$HADOOP_VER hadoop && ln -s ./spark-$SPARK_VER-bin-hadoop3.2 spark2-client

USER root

RUN conda install mamba -n base -c conda-forge && \
    mamba install --yes --quiet -c conda-forge \
    'jupyter' \
    'r-devtools' \
    'r-stringr' \
    'r-argparse' && \
    mamba clean -y --all &&\
    fix-permissions $ANACONDA_HOME && \
    fix-permissions /home/$NB_USER

USER $NB_UID

#Package ‘SparkR’ currently supports 3.1.2, so we'll set its own ARG
#https://cran.r-project.org/src/contrib/Archive/SparkR/

RUN Rscript -e 'install.packages("IRkernel", repos="https://mirror.las.iastate.edu/CRAN/", lib="/opt/conda/lib/R/library")' \
            -e 'IRkernel::installspec(prefix = "/usr/local")' \
            -e 'download.file(url = "https://cran.r-project.org/src/contrib/Archive/SparkR/SparkR_$SPARKR_VERSION.tar.gz", destfile = "SparkR_$SPARKR_VERSION.tar.gz")' \
            -e 'install.packages(pkgs="SparkR_$SPARKR_VERSION.tar.gz", type="source", repos=NULL, lib="/opt/conda/lib/R/library")' \
            -e 'unlink("SparkR_$SPARKR_VERSION.tar.gz")'

# SETUP HADOOP CONFIGS
RUN sed -i '/^export JAVA_HOME/ s:.*:export JAVA_HOME=/usr/lib/jvm/java\nexport HADOOP_HOME=/usr/hdp/current/hadoop\nexport HADOOP_HOME=/usr/hdp/current/hadoop\n:' $HADOOP_HOME/etc/hadoop/hadoop-env.sh
RUN sed -i '/^export HADOOP_CONF_DIR/ s:.*:export HADOOP_CONF_DIR=/usr/hdp/current/hadoop/etc/hadoop/:' $HADOOP_HOME/etc/hadoop/hadoop-env.sh
# SETUP PSEUDO - DISTRIBUTED CONFIGS FOR HADOOP
COPY ["core-site.xml.template", "hdfs-site.xml", "mapred-site.xml", "yarn-site.xml.template", \
      "$HADOOP_HOME/etc/hadoop/"]

# working around docker.io build error
RUN ls -la /usr/hdp/current/hadoop/etc/hadoop/*-env.sh && \
    chmod +x /usr/hdp/current/hadoop/etc/hadoop/*-env.sh && \
    ls -la /usr/hdp/current/hadoop/etc/hadoop/*-env.sh

# Install Toree
RUN cd /tmp && \
    curl -O https://archive.apache.org/dist/incubator/toree/0.5.0-incubating/toree-pip/toree-0.5.0.tar.gz && \
    pip install --upgrade setuptools --user && \
    pip install /tmp/toree-0.5.0.tar.gz && \
    jupyter toree install --spark_home=$SPARK_HOME --kernel_name="Spark $SPARK_VER" --interpreters=Scala && \
    rm -f /tmp/toree-0.5.0.tar.gz && \
    fix-permissions $ANACONDA_HOME && \
    fix-permissions /home/$NB_USER

# SETUP PASSWORDLESS SSH FOR $NB_USER
RUN ssh-keygen -q -N "" -t rsa -f /home/$NB_USER/.ssh/id_rsa && \
    cp /home/$NB_USER/.ssh/id_rsa.pub /home/$NB_USER/.ssh/authorized_keys && \
    chmod 0700 /home/$NB_USER

USER root

# SETUP PASSWORDLESS SSH
RUN yes y | ssh-keygen -q -N "" -t dsa -f /etc/ssh/ssh_host_dsa_key && \
    yes y | ssh-keygen -q -N "" -t rsa -f /etc/ssh/ssh_host_rsa_key && \
    yes y | ssh-keygen -q -N "" -t rsa -f /root/.ssh/id_rsa && \
    cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys

RUN ssh-keygen -A
COPY ssh_config /root/.ssh/config
RUN chmod 600 /root/.ssh/config && \
    chown root:root /root/.ssh/config && \
    echo "Port 2122" >> /etc/ssh/sshd_config && \
    echo "${NB_USER} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
RUN service ssh restart

COPY ssh_config /home/$NB_USER/.ssh/config
RUN chmod 600 /home/$NB_USER/.ssh/config && \
    chown $NB_USER: /home/$NB_USER/.ssh/config

COPY bootstrap-yarn-spark.sh /usr/local/bin/
RUN chown $NB_USER: /usr/local/bin/bootstrap-yarn-spark.sh && \
    chmod 0700 /usr/local/bin/bootstrap-yarn-spark.sh

CMD ["/usr/local/bin/bootstrap-yarn-spark.sh"]

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

USER $NB_USER
