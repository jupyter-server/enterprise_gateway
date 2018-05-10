#!/usr/bin/env bash

if [ "${EG_IMPERSONATION_ENABLED}" = "True" ]; then
        IMPERSONATION_OPTS=""
        USER_CLAUSE="as user ${KERNEL_USERNAME:-UNSPECIFIED}"
else
        IMPERSONATION_OPTS=""
        USER_CLAUSE="on behalf of user ${KERNEL_USERNAME:-UNSPECIFIED}"
fi

echo
echo "Starting IPython kernel for Spark in Kubernetes mode ${USER_CLAUSE}"
echo

SPARK_HOME=/opt/spark
SPARK_MASTER_URL=k8s://https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT}
KUBE_LABELS="--conf spark.kubernetes.driver.label.app=enterprise-gateway --conf spark.kubernetes.driver.label.kernel_id=${KERNEL_ID}"
KERNEL_ENVS="--conf spark.kubernetes.driverEnv.EG_RESPONSE_ADDRESS=${EG_RESPONSE_ADDRESS} --conf spark.kubernetes.driverEnv.KERNEL_CONNECTION_FILENAME=${KERNEL_CONNECTION_FILENAME}"
SPARK_IMAGES="--conf spark.kubernetes.driver.docker.image=kubespark/spark-driver-py:v2.2.0-kubernetes-0.5.0 --conf spark.kubernetes.executor.docker.image=kubespark/spark-executor-py:v2.2.0-kubernetes-0.5.0"
SPARK_RSS="--conf spark.kubernetes.initcontainer.docker.image=kubespark/spark-init:v2.2.0-kubernetes-0.5.0 --conf spark.kubernetes.resourceStagingServer.uri=http://${KUBERNETES_SERVICE_HOST}"

SPARK_OPTS="--master ${SPARK_MASTER_URL} --deploy-mode cluster --name eg-${KERNEL_USERNAME} ${KUBE_LABELS} ${KERNEL_ENVS} ${SPARK_IMAGES} --conf spark.kubernetes.submission.waitAppCompletion=false"

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
     "${IMPERSONATION_OPTS}" \
     "${PROG_HOME}/scripts/launch_ipykernel.py" \
     "${LAUNCH_OPTS}"
set +x
