#!/usr/bin/env bash

echo
echo "Starting IPython kernel on Kubernetes cluster as user ${USER_CLAUSE}"
echo

PROG_HOME="$(cd "`dirname "$0"`"/..; pwd)"

# Build kubectl command...

ENV_RESPONSE_ADDRESS=$1
ENV_LANGUAGE=python

echo response_address=${ENV_RESPONSE_ADDRESS}
echo language=${ENV_LANGUAGE}


# Setup environment variables to convey into container...

set -x
eval exec \
     "kubectl " \
     "run " \
     "${KERNEL_ID} " \
     "--image=elyra/k8s-kernel:dev " \
     "--env=\"ENV_RESPONSE_ADDRESS=${ENV_RESPONSE_ADDRESS}\"" \
     "--env=\"ENV_LANGUAGE=${ENV_LANGUAGE}\""
set +x



