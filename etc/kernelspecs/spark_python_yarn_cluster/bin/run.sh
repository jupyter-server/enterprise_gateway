#!/usr/bin/env bash

echo
echo "Starting IPython kernel for Spark in Yarn Cluster mode as user ${KERNEL_USERNAME:-UNSPECIFIED}"
echo

if [ -z "${SPARK_HOME}" ]; then
  echo "SPARK_HOME must be set to the location of a Spark distribution!"
  exit 1
fi

PROG_HOME="$(cd "`dirname "$0"`"/..; pwd)"

set -x
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}" \
     "$@"
set +x
