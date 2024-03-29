#!/usr/bin/env bash

if [ "${EG_IMPERSONATION_ENABLED}" = "True" ]; then
#        IMPERSONATION_OPTS="--proxy-user ${KERNEL_USERNAME:-UNSPECIFIED}"
        USER_CLAUSE="as user ${KERNEL_USERNAME:-UNSPECIFIED}"
else
#        IMPERSONATION_OPTS=""
        USER_CLAUSE="on behalf of user ${KERNEL_USERNAME:-UNSPECIFIED}"
fi

echo
echo "Starting Toree kernel for Spark in Kubernetes mode ${USER_CLAUSE}"
echo

if [ -z "${SPARK_HOME}" ]; then
  echo "SPARK_HOME must be set to the location of a Spark distribution!"
  exit 1
fi

if [ -z "${KERNEL_ID}" ]; then
  echo "KERNEL_ID must be set for discovery and lifecycle management!"
  exit 1
fi

KERNEL_LAUNCHERS_DIR=${KERNEL_LAUNCHERS_DIR:-/usr/local/bin/kernel-launchers}
PROG_HOME=${KERNEL_LAUNCHERS_DIR}/scala
KERNEL_ASSEMBLY=`(cd "${PROG_HOME}/lib"; ls -1 toree-assembly-*.jar;)`
TOREE_ASSEMBLY="${PROG_HOME}/lib/${KERNEL_ASSEMBLY}"
if [ ! -f ${TOREE_ASSEMBLY} ]; then
    echo "Toree assembly '${PROG_HOME}/lib/toree-assembly-*.jar' is missing.  Exiting..."
    exit 1
fi

# The SPARK_OPTS values during installation are stored in __TOREE_SPARK_OPTS__. This allows values to be specified during
# install, but also during runtime. The runtime options take precedence over the install options.
if [ "${SPARK_OPTS}" = "" ]; then
   SPARK_OPTS=${__TOREE_SPARK_OPTS__}
fi

if [ "${TOREE_OPTS}" = "" ]; then
   TOREE_OPTS=${__TOREE_OPTS__}
fi

# Toree launcher jar path, plus required lib jars (toree-assembly)
JARS="local://${TOREE_ASSEMBLY}"
# Toree launcher app path
LAUNCHER_JAR=`(cd "${PROG_HOME}/lib"; ls -1 toree-launcher*.jar;)`
LAUNCHER_APP="${PROG_HOME}/lib/${LAUNCHER_JAR}"
if [ ! -f ${LAUNCHER_APP} ]; then
    echo "Scala launcher jar '${PROG_HOME}/lib/toree-launcher*.jar' is missing.  Exiting..."
    exit 1
fi

EG_POD_TEMPLATE_DIR=${EG_POD_TEMPLATE_DIR:-/tmp}
SCRIPTS_HOME="$(cd "`dirname "$0"`"/../scripts; pwd)"
pod_template_file=${EG_POD_TEMPLATE_DIR}/kpt_${KERNEL_ID}
spark_opts_out=${EG_POD_TEMPLATE_DIR}/spark_opts_${KERNEL_ID}
python ${SCRIPTS_HOME}/launch_kubernetes.py $@ --pod-template=${pod_template_file} --spark-opts-out=${spark_opts_out}
additional_spark_opts=`cat ${spark_opts_out}`
SPARK_OPTS="${SPARK_OPTS} ${additional_spark_opts}"
rm -f ${spark_opts_out}

set -x
eval exec "${IMPERSONATION_OPTS}" \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     --jars "${JARS}" \
     --class launcher.ToreeLauncher \
     "local://${LAUNCHER_APP}" \
     "${TOREE_OPTS}" \
     "${LAUNCH_OPTS}" \
     "$@"
set +x
