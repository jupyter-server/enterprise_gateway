#!/usr/bin/env bash

echo
echo "Starting IPython kernel for Spark in Kubernetes mode ${USER_CLAUSE}"
echo

if [ -z "${SPARK_HOME}" ]; then
  echo "SPARK_HOME must be set to the location of a Spark distribution!"
  exit 1
fi

if [ -z "${KERNEL_ID}" ]; then
  echo "KERNEL_ID must be set for discovery and lifecycle management!"
  exit 1
fi

# FIXME: Seems like a bug - but the kernel won't launch w/o a --jars option.  Adding in here rather than kernel.json
JAR_FILES="--jars local:///opt/spark/examples/jars/spark-examples_2.11-2.2.0-k8s-0.5.0.jar"

PROG_HOME="$(cd "`dirname "$0"`"/..; pwd)"

set -x
eval exec \
     "${SPARK_HOME}/bin/spark-submit" \
     "${SPARK_OPTS}" \
     "${JAR_FILES}" \
     "local://${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}" \
     "$@"
set +x
