#!/bin/bash

# This file is a copy of /etc/bootstrap.sh but sets up the YARN cluster in its "deamon" case.
# It also checks for --help or no options before starting anything...

FROM=${FROM:-"YARN"}

CMD=${1:-"--help"}
if [[ "$CMD" == "--help" ]];
then
	echo ""
	echo "usage: docker run {-it|-d} --rm -h <container-hostname> -p 8088:8088 -p 8042:8042 <docker-opts> <docker-image> <command>"
	echo ""
	echo "where <command> is:"
	echo "    --yarn  ... Runs container as standalone YARN master - assumed to be used with Enterprise Gateway"
	echo "    --help  ... Produces this message."
	echo "    <other> ... Invokes '<other>'.  Use <other>='/bin/bash' to explore within the container."
	echo ""
	echo "Tips:"
	echo "1) You can target a different YARN cluster by using '-e YARN_HOST=<myOtherYarnMaster>'"
	echo "2) You can \"bring your own kernels\" by mounting to /tmp/byok/kernels (e.g., -v my-kernels-dir:/tmp/byok/kernels)"
	echo "3) It is advised that ports '8088' and '8042' be mapped to host ports, although the host port numbers are not"
	echo "   required to be '8088' and '8042'. "
	exit 0
fi

: ${HADOOP_HOME:=/usr/hdp/current/hadoop}
: ${YARN_HOST:=$HOSTNAME}
: ${SPARK_HOME:=/usr/hdp/current/spark2-client}
: ${SPARK_VER:=3.2.1}
: ${JAVA_HOME:=/usr/lib/jvm/java}

echo "export JAVA_HOME=${JAVA_HOME}" >> $HADOOP_HOME/etc/hadoop/hadoop-env.sh

# Set all the hadoop envs for this shell
$HADOOP_HOME/etc/hadoop/hadoop-env.sh

rm -f /tmp/*.pid

# installing libraries if any - (resource urls added comma separated to the ACP system variable)
cd $HADOOP_HOME/share/hadoop/common ; for cp in ${ACP//,/ }; do  echo == $cp; curl -LO $cp ; done; cd -

## altering the hostname in core-site and enterprise-gateway startup configuration
sed s/HOSTNAME/$YARN_HOST/ /usr/hdp/current/hadoop/etc/hadoop/core-site.xml.template > /usr/hdp/current/hadoop/etc/hadoop/core-site.xml
sed s/HOSTNAME/$YARN_HOST/ /usr/hdp/current/hadoop/etc/hadoop/yarn-site.xml.template > /usr/hdp/current/hadoop/etc/hadoop/yarn-site.xml
#
# setting spark defaults
cp $SPARK_HOME/conf/spark-defaults.conf.template  $SPARK_HOME/conf/spark-defaults.conf
# set spark.yarn.jars so spark will stop uploaded jars to hdfs everytime
echo "spark.yarn.jars hdfs://$YARN_HOST:9000/spark/*.jar" >>  $SPARK_HOME/conf/spark-defaults.conf
# place metastore db and derby.log in /tmp
echo "spark.driver.extraJavaOptions -Dderby.system.home=/tmp" >>  $SPARK_HOME/conf/spark-defaults.conf

##/usr/sbin/rsyslog
echo "********** STARTING SSH DAEMON ***********"
sudo service ssh restart

# If we're not running in standalone mode, don't run as jovyan.
# If we're running in standalone mode, startup yarn, hdfs, etc.
if [[ "$YARN_HOST" == "$HOSTNAME" || "$FROM" == "YARN" ]];
then
    echo "********** FORMATTING NAMENODE ***********"
    $HADOOP_HOME/bin/hdfs namenode -format
    $HADOOP_HOME/sbin/start-dfs.sh
    $HADOOP_HOME/sbin/start-yarn.sh

    echo "********** LEAVING HDFS SAFE MODE...... ***********"
    $HADOOP_HOME/bin/hadoop dfsadmin -safemode leave

    echo "********** UPLOADING SPARK JARS TO HDFS..... ***********"
    hdfs dfs -put $SPARK_HOME/jars /spark

    ## Add HDFS folders for our users (jovyan, bob, alice)...
    echo "Setting up HDFS folders for Enterprise Gateway users..."
    hdfs dfs -mkdir -p /user/{jovyan,bob,alice,root} /tmp/hive
    hdfs dfs -chown jovyan:jovyan /user/jovyan
    hdfs dfs -chown bob:bob /user/bob
    hdfs dfs -chown alice:alice /user/alice
    hdfs dfs -chmod 0777 /tmp/hive

elif [[ "$CMD" == "--yarn" ]];
then
    echo "YARN_HOST cannot be different from HOSTNAME when using --yarn! YARN_HOST=$YARN_HOST != HOSTNAME=$HOSTNAME"
    exit 1
fi

if [[ "$CMD" == "--yarn" ]];
then
    echo "YARN application logs can be found at '/usr/hdp/current/hadoop/logs/userlogs'"
    prev_count=0
    while [ 1 ]
    do
        # Every minute list any new application directories that have been created since
        # last time.
        sleep 60
        if ls -ld /usr/hdp/current/hadoop/logs/userlogs/application* > /dev/null 2>&1;
        then
            count=`ls -ld /usr/hdp/current/hadoop/logs/userlogs/application*|wc -l`
            if [[ $count > $prev_count ]];
            then
                new_apps=`expr $count - $prev_count`
                ls -ldt /usr/hdp/current/hadoop/logs/userlogs/application*|head --lines=$new_apps
            fi
            # reset each time in case count < prev_count
            prev_count=$count
        fi
    done
elif [[ "$FROM" == "YARN" ]];
then
    echo ""
    echo "Note:  YARN application logs can be found at '/usr/hdp/current/hadoop/logs/userlogs'"
    "$*"
fi

exit 0
