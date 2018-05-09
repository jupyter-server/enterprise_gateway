#!/usr/bin/env bash

if [ "${EG_IMPERSONATION_ENABLED}" = "True" ]; then
        IMPERSONATION_OPTS="sudo PATH=${PATH} -H -E -u ${KERNEL_USERNAME:-UNSPECIFIED}"
        USER_CLAUSE="as user ${KERNEL_USERNAME:-UNSPECIFIED}"
else
        IMPERSONATION_OPTS=""
        USER_CLAUSE="on behalf of user ${KERNEL_USERNAME:-UNSPECIFIED}"
fi

echo
echo "Starting IPython kernel for Spark Cluster mode ${USER_CLAUSE}"
echo

if [ -z "${SPARK_HOME}" ]; then
  echo "SPARK_HOME must be set to the location of a Spark distribution!"
  exit 1
fi

PROG_HOME="$(cd "`dirname "$0"`"/..; pwd)"

eval exec "${IMPERSONATION_OPTS}" \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}" \
     "$@"
