#!/bin/bash

echo kernel-bootstrap.sh: language=${KERNEL_LANGUAGE}, connection-file=${KERNEL_CONNECTION_FILENAME}, reponse-addr=${EG_RESPONSE_ADDRESS}, no-spark-context-opt=${KERNEL_NO_SPARK_CONTEXT_OPT}

if [[ "${KERNEL_LANGUAGE}" == "python" ]];
then
	echo "python /usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} ${KERNEL_NO_SPARK_CONTEXT_OPT}"
	python /usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} ${KERNEL_NO_SPARK_CONTEXT_OPT}
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0
