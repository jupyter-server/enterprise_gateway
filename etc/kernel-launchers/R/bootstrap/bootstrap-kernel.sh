#!/bin/bash

KERNEL_LAUNCHERS_PATH=/usr/local/share/jupyter/kernel-launchers

echo kernel-bootstrap.sh env: `env`

if [[ "${KERNEL_LANGUAGE}" == "r" ]];
then
	echo "Rscript ${KERNEL_LAUNCHERS_PATH}/R/scripts/launch_IRkernel.R ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}"
	Rscript ${KERNEL_LAUNCHERS_PATH}/R/scripts/launch_IRkernel.R ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0
