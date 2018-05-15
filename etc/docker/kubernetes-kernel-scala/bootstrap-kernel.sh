#!/bin/bash

echo kernel-bootstrap.sh: language=${KERNEL_LANGUAGE}, connection-file=${KERNEL_CONNECTION_FILENAME}, reponse-addr=${EG_RESPONSE_ADDRESS}, no-spark-context-opt=${KERNEL_NO_SPARK_CONTEXT_OPT}

if [[ "${KERNEL_LANGUAGE}" != "scala" ]];
then
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi

PROG_HOME=/usr/local/share/jupyter/kernels/scala_kubernetes
KERNEL_ASSEMBLY=`(cd "${PROG_HOME}/lib"; ls -1 toree-assembly-*.jar;)`
TOREE_ASSEMBLY="${PROG_HOME}/lib/${KERNEL_ASSEMBLY}"

# Toree launcher jar path, plus required lib jars (toree-assembly)
JARS="${TOREE_ASSEMBLY}"
# Toree launcher app path
LAUNCHER_JAR=`(cd "${PROG_HOME}/lib"; ls -1 toree-launcher*.jar;)`
LAUNCHER_APP="${PROG_HOME}/lib/${LAUNCHER_JAR}"

SPARK_OPTS=""
TOREE_OPTS="--alternate-sigint USR2"

set -x
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     --jars "${JARS}" \
     --class launcher.ToreeLauncher \
     "${LAUNCHER_APP}" \
     "${TOREE_OPTS}" \
     "--profile ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} ${KERNEL_NO_SPARK_CONTEXT_OPT}"
set +x

exit 0
