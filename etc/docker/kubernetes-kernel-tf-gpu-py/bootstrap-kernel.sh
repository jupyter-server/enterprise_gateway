#!/bin/bash

echo kernel-bootstrap.sh: language=${KERNEL_LANGUAGE}, connection-file=${KERNEL_CONNECTION_FILENAME}, reponse-addr=${EG_RESPONSE_ADDRESS}, spark-context-init-mode=${KERNEL_SPARK_CONTEXT_INIT_MODE}

if [[ "${KERNEL_LANGUAGE}" == "python" ]];
then
	echo "python /usr/local/share/jupyter/kernels/python_tf_gpu_kubernetes/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}"
	python /usr/local/share/jupyter/kernels/python_tf_gpu_kubernetes/scripts/launch_ipykernel.py ${KERNEL_CONNECTION_FILENAME} --RemoteProcessProxy.response-address ${EG_RESPONSE_ADDRESS} --RemoteProcessProxy.spark-context-initialization-mode ${KERNEL_SPARK_CONTEXT_INIT_MODE}
else
	echo "Unrecognized value for KERNEL_LANGUAGE: '${KERNEL_LANGUAGE}'!"
	exit 1
fi
exit 0
