#!/bin/bash

# This file is a copy of /etc/bootstrap.sh but invokes Jupyter Enterprise Gateway in its "deamon" case.
# It also checks for --help or no options before starting anything...


CMD=${1:-"--help"}
if [[ "$CMD" == "--help" ]];
then
	echo ""
	echo "usage: docker run -h <container-hostname> -p 8888:8888 -p 8088:8088 -p 8042:8042 <docker-opts> <docker-image> <command>"
	echo ""
	echo "where <command> is:"
	echo "    --elyra ... Invokes Enterprise Gateway as user 'elyra' directly.  Useful for daemon behavior."
	echo "    --help  ... Produces this message."
	echo "    <other> ... Invokes '/bin/bash -c <other>'.  Use <other>='bash' to explore within the container."
	echo ""
	echo "NOTE: It is advised that port '8888' be mapped to a host port, although the host port number is not"
	echo "      required to be '8888'.  Mapping of ports '8088' and '8042' is also strongly recommended"
	echo "      for YARN application monitoring."
	exit 0
fi

: ${HADOOP_PREFIX:=/usr/local/hadoop}

$HADOOP_PREFIX/etc/hadoop/hadoop-env.sh

rm /tmp/*.pid

# installing libraries if any - (resource urls added comma separated to the ACP system variable)
cd $HADOOP_PREFIX/share/hadoop/common ; for cp in ${ACP//,/ }; do  echo == $cp; curl -LO $cp ; done; cd -

# altering the hostname in core-site and enterprise-gateway startup configuration
sed s/HOSTNAME/$HOSTNAME/ /usr/local/hadoop/etc/hadoop/core-site.xml.template > /usr/local/hadoop/etc/hadoop/core-site.xml
sed s/HOSTNAME/$HOSTNAME/ /usr/local/share/jupyter/start-enterprise-gateway.sh.template > /usr/local/share/jupyter/start-enterprise-gateway.sh
chmod 0755 /usr/local/share/jupyter/start-enterprise-gateway.sh

# setting spark defaults
cp $SPARK_HOME/conf/spark-defaults.conf.template  $SPARK_HOME/conf/spark-defaults.conf

cp $SPARK_HOME/conf/metrics.properties.template $SPARK_HOME/conf/metrics.properties

service rsyslog start
service rsyslog status
service sshd restart
service sshd status
$HADOOP_PREFIX/sbin/start-dfs.sh
$HADOOP_PREFIX/sbin/start-yarn.sh

# Add HDFS folders for our users (elyra, bob, alice)...
echo "Waiting for Namenode to exit safemode..."
hdfs dfsadmin -safemode wait
echo "Setting up HDFS folders for Enterprise Gateway users..."
hdfs dfs -mkdir -p /user/{elyra,bob,alice} /tmp/hive
hdfs dfs -chown elyra:elyra /user/elyra
hdfs dfs -chown bob:bob /user/bob
hdfs dfs -chown alice:alice /user/alice
hdfs dfs -chmod 0777 /tmp/hive


CMD=${1:-"--help"}
if [[ "$CMD" == "--elyra" ]];
then
	sudo -u elyra /usr/local/share/jupyter/start-enterprise-gateway.sh
else
	echo ""
	echo "Note: Enterprise Gateway can be manually started using 'sudo -u elyra /usr/local/share/jupyter/start-enterprise-gateway.sh'..."
	echo "      YARN application logs can be found at '/usr/local/hadoop-2.7.1/logs/userlogs'"
	/bin/bash -c "$*"
fi
exit 0