#!/bin/bash

echo kernel-bootstrap.sh: language=${KERNEL_LANGUAGE}, connection-file=${KERNEL_CONNECTION_FILENAME}, reponse-addr=${EG_RESPONSE_ADDRESS}, no-spark-context=${NO_SPARK_CONTEXT}

if [[ "${KERNEL_LANGUAGE}" == "python" ]];
then
	echo "python /usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} ${NO_SPARK_CONTEXT}"
	python /usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} ${NO_SPARK_CONTEXT}
elif [[ "${KERNEL_LANGUAGE}" == "scala" ]];
then
	echo "KERNEL_LANGUAGE '${KERNEL_LANGUAGE}' is not yet supported."
elif [[ "${KERNEL_LANGUAGE}" == "R" ]];
then
	echo "KERNEL_LANGUAGE '${KERNEL_LANGUAGE}' is not yet supported."
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0
