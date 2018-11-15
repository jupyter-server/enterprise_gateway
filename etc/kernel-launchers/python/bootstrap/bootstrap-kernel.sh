#!/bin/bash

export JPY_PARENT_PID=$$  # Force reset of parent pid since we're detached

KERNEL_LAUNCHERS_PATH=/usr/local/share/jupyter/kernel-launchers

echo kernel-bootstrap.sh env: `env`

if [[ "${KERNEL_LANGUAGE}" == "python" ]];
then
	echo "python ${KERNEL_LAUNCHERS_PATH}/python/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}"
	python ${KERNEL_LAUNCHERS_PATH}/python/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0
