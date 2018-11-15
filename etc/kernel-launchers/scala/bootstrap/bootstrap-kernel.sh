#!/bin/bash

KERNEL_LAUNCHERS_PATH=/usr/local/share/jupyter/kernel-launchers

echo kernel-bootstrap.sh env: `env`

if [[ "${KERNEL_LANGUAGE}" != "scala" ]];
then
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi

PROG_HOME=${KERNEL_LAUNCHERS_PATH}/scala
KERNEL_ASSEMBLY=`(cd "${PROG_HOME}/lib"; ls -1 toree-assembly-*.jar;)`
TOREE_ASSEMBLY="${PROG_HOME}/lib/${KERNEL_ASSEMBLY}"
if [ ! -f ${TOREE_ASSEMBLY} ]; then
    echo "Toree assembly '${PROG_HOME}/lib/toree-assembly-*.jar' is missing.  Exiting..."
    exit 1
fi

# Toree launcher jar path, plus required lib jars (toree-assembly)
JARS="${TOREE_ASSEMBLY}"
# Toree launcher app path
LAUNCHER_JAR=`(cd "${PROG_HOME}/lib"; ls -1 toree-launcher*.jar;)`
LAUNCHER_APP="${PROG_HOME}/lib/${LAUNCHER_JAR}"
if [ ! -f ${LAUNCHER_APP} ]; then
    echo "Scala launcher jar '${PROG_HOME}/lib/toree-launcher*.jar' is missing.  Exiting..."
    exit 1
fi

SPARK_OPTS="--name ${KERNEL_USERNAME}-${KERNEL_ID}"
TOREE_OPTS="--alternate-sigint USR2"

set -x
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     --jars "${JARS}" \
     --class launcher.ToreeLauncher \
     "${LAUNCHER_APP}" \
     "${TOREE_OPTS}" \
     "--profile ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}"
set +x

exit 0
