#!/bin/bash

#export ANACONDA_HOME=/opt/conda
#export JAVA_HOME=/usr/java/default
#export PYSPARK_PYTHON=${ANACONDA_HOME}/bin/python
#export PATH=${ANACONDA_HOME}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${JAVA_HOME}/bin

# Enterprise Gateway variables
export EG_SSH_PORT=${EG_SSH_PORT:-2122}
export KG_IP=${KG_IP:-0.0.0.0}
export KG_PORT=${KG_PORT:-8888}
export KG_PORT_RETRIES=${KG_PORT_RETRIES:-0}

# To use tunneling set this variable to 'True' (may need to run as root).
export EG_ENABLE_TUNNELING=${EG_ENABLE_TUNNELING:-False}

export EG_LOG_LEVEL=${EG_LOG_LEVEL:-DEBUG}
export EG_CULL_IDLE_TIMEOUT=${EG_CULL_IDLE_TIMEOUT:-43200}  # default to 12 hours
export EG_CULL_INTERVAL=${EG_CULL_INTERVAL:-60}
export EG_CULL_CONNECTED=${EG_CULL_CONNECTED:-False}
export EG_KERNEL_WHITELIST=${EG_KERNEL_WHITELIST:-"['r_docker','python_docker','python_tf_docker','scala_docker','spark_r_docker','spark_python_docker','spark_scala_docker']"}


echo "Starting Jupyter Enterprise Gateway..."

jupyter enterprisegateway \
	--log-level=${EG_LOG_LEVEL} \
	--KernelSpecManager.whitelist=${EG_KERNEL_WHITELIST} \
	--MappingKernelManager.cull_idle_timeout=${EG_CULL_IDLE_TIMEOUT} \
	--MappingKernelManager.cull_interval=${EG_CULL_INTERVAL} \
	--MappingKernelManager.cull_connected=${EG_CULL_CONNECTED} 2>&1 | tee /usr/local/share/jupyter/enterprise-gateway.log


