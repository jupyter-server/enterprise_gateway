#!/bin/bash

# This file is used to deploy Enterprise Gateway as a traditional docker container.
# We should convert this to a Docker Compose file at some point.
# First a docker overlay network is created and referenced by the service.  This network
# must also get conveyed to launched kernel containers and that occurs via the env variable: EG_DOCKER_NETWORK

export KG_PORT=${KG_PORT:-8888}
export EG_DOCKER_NETWORK=${EG_DOCKER_NETWORK:-enterprise-gateway}
export EG_KERNEL_WHITELIST=${EG_KERNEL_WHITELIST:-"['r_docker','python_docker','python_tf_docker','python_tf_gpu_docker','scala_docker']"}
export EG_NAME=${EG_NAME:-enterprise-gateway}

# It's often helpful to mount the kernelspec files from the host into the container.
MOUNT_KERNELSPECS=
#MOUNT_KERNELSPECS="-v /usr/local/share/jupyter/kernels:/usr/local/share/jupyter/kernels"

# Create the overlay network
docker network create --label app=enterprise-gateway -d overlay ${EG_DOCKER_NETWORK}

# Notes (FIXMEs):
# 1. We need to address the need to run as UID 0 (root).  This appears to be required inorder to create containers/services from within.

# Ensure the following VERSION tag is updated to the version of Enterprise Gateway you wish to run
docker run -d -it \
	--network ${EG_DOCKER_NETWORK} \
	-l app=enterprise-gateway -l component=enterprise-gateway \
	-e EG_DOCKER_NETWORK=${EG_DOCKER_NETWORK} -e EG_KERNEL_LAUNCH_TIMEOUT=60 -e EG_KERNEL_WHITELIST=${EG_KERNEL_WHITELIST} -e KG_PORT=${KG_PORT} \
	${MOUNT_KERNELSPECS} \
	-u 0 -v /var/run/docker.sock:/var/run/docker.sock \
	-p ${KG_PORT}:${KG_PORT} \
	--name ${EG_NAME} \
	elyra/enterprise-gateway:VERSION --elyra
