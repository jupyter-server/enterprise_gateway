#!/usr/bin/env bash

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

PROG_HOME="$(cd "`dirname "$0"`"/..; pwd)"

set -x
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "local://${PROG_HOME}/scripts/launch_IRkernel.R" \
     "${LAUNCH_OPTS}" \
     "$@"
set +x
