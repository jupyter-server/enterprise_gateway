#!/bin/bash

#export ANACONDA_HOME=/opt/conda
#export JAVA_HOME=/usr/java/default
#export PYSPARK_PYTHON=${ANACONDA_HOME}/bin/python
#export PATH=${ANACONDA_HOME}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${JAVA_HOME}/bin

# Enterprise Gateway variables
export EG_SSH_PORT=${EG_SSH_PORT:-2122}

# Kernel Gateway looks for KG_ for the following.  For the sake of consistency
# we want to use EG_.  The following produces the default value in EG_ (unless
# set in the env), with the ultimate override of KG_ from the env.
export EG_IP=${EG_IP:-0.0.0.0}
export KG_IP=${KG_IP:-${EG_IP}}
export EG_PORT=${EG_PORT:-8888}
export KG_PORT=${KG_PORT:-${EG_PORT}}
export EG_PORT_RETRIES=${EG_PORT_RETRIES:-0}
export KG_PORT_RETRIES=${KG_PORT_RETRIES:-${EG_PORT_RETRIES}}

# To use tunneling set this variable to 'True' (may need to run as root).
export EG_ENABLE_TUNNELING=${EG_ENABLE_TUNNELING:-False}

export EG_LIST_KERNELS=${EG_LIST_KERNELS:-True}
export EG_LOG_LEVEL=${EG_LOG_LEVEL:-DEBUG}
export EG_CULL_IDLE_TIMEOUT=${EG_CULL_IDLE_TIMEOUT:-43200}  # default to 12 hours
export EG_CULL_INTERVAL=${EG_CULL_INTERVAL:-60}
export EG_CULL_CONNECTED=${EG_CULL_CONNECTED:-False}
EG_ALLOWED_KERNELS=${EG_ALLOWED_KERNELS:-${EG_KERNEL_WHITELIST:-"null"}}
export EG_ALLOWED_KERNELS=`echo ${EG_ALLOWED_KERNELS} | sed 's/[][]//g'` # sed is used to strip off surrounding brackets as they should no longer be included.
export EG_DEFAULT_KERNEL_NAME=${EG_DEFAULT_KERNEL_NAME:-python_docker}
export EG_KERNEL_INFO_TIMEOUT=${EG_KERNEL_INFO_TIMEOUT:-60}

# Determine whether the kernels-allowed list should be added to the start command.
# This is conveyed via a 'null' value for the env - which indicates no kernel names
# were used in the helm chart or docker-compose yaml.
allowed_kernels_option=""
if [ "${EG_ALLOWED_KERNELS}" != "null" ]; then
  # Update to --KernelSpecManager.allowed_kernelspecs once jupyter_client >= 7 can be supported
	allowed_kernels_option="--KernelSpecManager.whitelist=[${EG_ALLOWED_KERNELS}]"
fi

echo "Starting Jupyter Enterprise Gateway..."

exec jupyter enterprisegateway \
	--log-level=${EG_LOG_LEVEL} ${allowed_kernels_option} \
	--RemoteMappingKernelManager.cull_idle_timeout=${EG_CULL_IDLE_TIMEOUT} \
	--RemoteMappingKernelManager.cull_interval=${EG_CULL_INTERVAL} \
	--RemoteMappingKernelManager.cull_connected=${EG_CULL_CONNECTED} \
	--RemoteMappingKernelManager.default_kernel_name=${EG_DEFAULT_KERNEL_NAME} \
	--RemoteMappingKernelManager.kernel_info_timeout=${EG_KERNEL_INFO_TIMEOUT}
