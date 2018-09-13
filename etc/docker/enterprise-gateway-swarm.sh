#!/bin/bash

# This file is used to deploy Enterprise Gateway as a service in a Docker Swarm cluster.
# We should convert this to a Docker Compose file at some point.
# First a docker overlay network is created and referenced by the service.  This network
# must also get conveyed to launched kernel containers and that occurs via the env variable: EG_DOCKER_NETWORK

export KG_PORT=${KG_PORT:-8888}
export EG_DOCKER_NETWORK=${EG_DOCKER_NETWORK:-enterprise-gateway}
export EG_KERNEL_WHITELIST=${EG_KERNEL_WHITELIST:-"['r_docker','python_docker','python_tf_docker','python_tf_gpu_docker','scala_docker']"}
export EG_NAME=${EG_NAME:-enterprise-gateway}

# It's often helpful to mount the kernelspec files from the host into the container.  Since this is a swarm,
# it is recommended that these be mounted on an NFS volume available to all nodes of the cluster.
MOUNT_KERNELSPECS=
#MOUNT_KERNELSPECS="--mount type=bind,src=/usr/local/share/jupyter/kernels,dst=/usr/local/share/jupyter/kernels"

# Create the overlay network
docker network create --label app=enterprise-gateway -d overlay ${EG_DOCKER_NETWORK}

# Notes (FIXMEs):
# 1. We need to address the need to run as UID 0 (root).  This appears to be required inorder to create containers/services from within.
# 2. Using endpoint-mode dnsrr (which appears to be required inorder for kernel container to send the connection info response back) 
# also required mode=host on any published ports. :-(
# 3. We only use one replica since session affinity is another point of investigation in Swarm

docker service create \
	--endpoint-mode dnsrr --network ${EG_DOCKER_NETWORK} \
	--replicas 1 \
	-l app=enterprise-gateway -l component=enterprise-gateway \
	-e EG_DOCKER_NETWORK=${EG_DOCKER_NETWORK} -e EG_KERNEL_LAUNCH_TIMEOUT=60 -e EG_CULL_IDLE_TIMEOUT=180 -e EG_KERNEL_WHITELIST=${EG_KERNEL_WHITELIST} -e KG_PORT=${KG_PORT} \
	${MOUNT_KERNELSPECS} \
	-u 0 --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock \
	--publish published=${KG_PORT},target=${KG_PORT},mode=host \
	--name ${EG_NAME} \
	elyra/enterprise-gateway:dev --elyra
