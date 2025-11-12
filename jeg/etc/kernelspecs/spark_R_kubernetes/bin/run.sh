#!/usr/bin/env bash

if [ "${EG_IMPERSONATION_ENABLED}" = "True" ]; then
#        IMPERSONATION_OPTS="--proxy-user ${KERNEL_USERNAME:-UNSPECIFIED}"
        USER_CLAUSE="as user ${KERNEL_USERNAME:-UNSPECIFIED}"
else
#        IMPERSONATION_OPTS=""
        USER_CLAUSE="on behalf of user ${KERNEL_USERNAME:-UNSPECIFIED}"
fi

echo
echo "Starting IRkernel for Spark in Kubernetes mode ${USER_CLAUSE}"
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
PROG_HOME=${KERNEL_LAUNCHERS_DIR}/R

EG_POD_TEMPLATE_DIR=${EG_POD_TEMPLATE_DIR:-/tmp}
SCRIPTS_HOME="$(cd "`dirname "$0"`"/../scripts; pwd)"
pod_template_file=${EG_POD_TEMPLATE_DIR}/kpt_${KERNEL_ID}
spark_opts_out=${EG_POD_TEMPLATE_DIR}/spark_opts_${KERNEL_ID}
python ${SCRIPTS_HOME}/launch_kubernetes.py $@ --pod-template=${pod_template_file} --spark-opts-out=${spark_opts_out}
additional_spark_opts=`cat ${spark_opts_out}`
SPARK_OPTS="${SPARK_OPTS} ${additional_spark_opts}"
rm -f ${spark_opts_out}

set -x
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "local://${PROG_HOME}/scripts/launch_IRkernel.R" \
     "${LAUNCH_OPTS}" \
     "$@"
set +x
