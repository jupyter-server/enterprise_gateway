#!/bin/bash
set -e
pushd .
cd $EG_HOME
make clean dist;
#make clean-enterprise-gateway enterprise-gateway clean-kernel-ray-py kernel-ray-py HUB_ORG=lresende TAG=dev MULTIARCH_BUILD=true;
make clean-enterprise-gateway enterprise-gateway push-enterprise-gateway clean-kernel-ray-py kernel-ray-py push-kernel-ray-py HUB_ORG=lresende TAG=dev;
popd
minikube image load lresende/enterprise-gateway:dev;
minikube image load lresende/kernel-ray-py:dev;
kubectl --context=ray -n enterprise-gateway rollout restart deployment/enterprise-gateway;
minikube service --url proxy-public -n hub
