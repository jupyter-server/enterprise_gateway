# Copyright (c) Juper Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help clean docker-clean docker-clean-enterprise-gateway docker-clean-nb2kg docker-clean-yarn-spark docker-clean-kubernetes toree-launcher

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash

KERNELSPECS_FILE:=../dist/jupyter_enterprise_gateway_kernelspecs-$(VERSION).tar.gz
KERNELSPECS_FILES:=$(shell find kernel-launchers/python kernel-launchers/R kernel-launchers/scala/toree-launcher/src -type f -name '*')
TOREE_LAUNCHER_FILES:=$(shell find kernel-launchers/scala/toree-launcher/src -type f -name '*')

ENTERPRISE_GATEWAY_TAG:=dev
NB2KG_TAG:=dev
YARN_SPARK_TAG:=2.1.0

NO_CACHE?=--no-cache

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

clean: ## Make a clean source tree
	-rm -rf kernel-launchers/scala/lib
	@(cd kernel-launchers/scala/toree-launcher; sbt $@)

kernelspecs: $(KERNELSPECS_FILE) ## Make a tar.gz file consisting of kernelspec files

$(KERNELSPECS_FILE): $(KERNELSPECS_FILES) kernel-launchers/scala/lib  
	@mkdir -p ../build/kernelspecs
	cp -r kernelspecs ../build
	@echo ../build/kernelspecs/*_python_* | xargs -t -n 1 cp -r kernel-launchers/python/*
	@echo ../build/kernelspecs/*_R_* | xargs -t -n 1 cp -r kernel-launchers/R/*
	@echo ../build/kernelspecs/*_scala_* | xargs -t -n 1 cp -r kernel-launchers/scala/lib
	@mkdir -p ../dist
	rm -f $(KERNELSPECS_FILE)
	@( cd ../build/kernelspecs; tar -pvczf "../$(KERNELSPECS_FILE)" * )

kernel-launchers/scala/lib: $(TOREE_LAUNCHER_FILES)
	-rm -rf kernel-launchers/scala/lib
	mkdir -p kernel-launchers/scala/lib
	@(cd kernel-launchers/scala/toree-launcher; sbt -Dversion=$(VERSION) package; cp target/scala-2.11/*.jar ../lib)
	
docker-images: docker-image-enterprise-gateway docker-image-nb2kg docker-image-yarn-spark docker-image-kubernetes-enterprise-gateway docker-image-kubernetes-kernels ## Build docker images

test-parent:
	@echo wheel=../$(WHEEL_FILE)
	@make -C .. bdist 

docker-image-enterprise-gateway: docker-image-yarn-spark ../.image-enterprise-gateway ## Build elyra/enterprise-gateway:dev docker image
../.image-enterprise-gateway: docker/enterprise-gateway/* ../$(WHEEL_FILE) $(KERNELSPECS_FILE)
	@make docker-clean-enterprise-gateway kernelspecs
	@make -C .. bdist
	@mkdir -p ../build/docker/enterprise-gateway
	cp docker/enterprise-gateway/* ../build/docker/enterprise-gateway
	cp ../dist/jupyter_enterprise_gateway* ../build/docker/enterprise-gateway
	@(cd ../build/docker/enterprise-gateway; docker build $(NO_CACHE) -t elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) . )
	@touch ../.image-enterprise-gateway
	@-docker images elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-image-nb2kg: ../.image-nb2kg ## Build elyra/nb2kg:dev docker image 
../.image-nb2kg: docker/nb2kg/* 
	@make docker-clean-nb2kg
	@mkdir -p ../build/docker/nb2kg
	cp docker/nb2kg/* ../build/docker/nb2kg
	@(cd ../build/docker/nb2kg; docker build $(NO_CACHE) -t elyra/nb2kg:$(NB2KG_TAG) . )
	@touch ../.image-nb2kg
	@-docker images elyra/nb2kg:$(NB2KG_TAG)

docker-image-yarn-spark: ../.image-yarn-spark ## Build elyra/yarn-spark:2.1.0 docker image
../.image-yarn-spark: docker/yarn-spark/*
	@make docker-clean-yarn-spark
	@mkdir -p ../build/docker/yarn-spark
	cp docker/yarn-spark/* ../build/docker/yarn-spark
	@(cd ../build/docker/yarn-spark; docker build $(NO_CACHE) -t elyra/yarn-spark:$(YARN_SPARK_TAG) . )
	@touch ../.image-yarn-spark
	@-docker images elyra/yarn-spark:$(YARN_SPARK_TAG)

docker-clean-enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
	@rm -f ../.image-enterprise-gateway
	@-docker rmi -f elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-clean-nb2kg: ## Remove elyra/nb2kg:dev docker image
	@rm -f ../.image-nb2kg
	@-docker rmi -f elyra/nb2kg:$(NB2KG_TAG)

docker-clean-yarn-spark: ## Remove elyra/yarn-spark:2.1.0 docker image
	@rm -f ../.image-yarn-spark
	@-docker rmi -f elyra/yarn-spark:$(YARN_SPARK_TAG)

## Kubernetes container images

docker-images-kubernetes: docker-image-kubernetes-enterprise-gateway docker-image-kubernetes-kerneles

docker-image-kubernetes-enterprise-gateway: ../.image-kubernetes-enterprise-gateway ## Build elyra/kubernetes-enterprise-gateway:dev docker image
../.image-kubernetes-enterprise-gateway: docker/kubernetes-enterprise-gateway/* ../$(WHEEL_FILE) $(KERNELSPECS_FILE)
	@make docker-clean-kubernetes-enterprise-gateway
	@make -C .. bdist
	@mkdir -p ../build/docker/kubernetes-enterprise-gateway
	cp docker/kubernetes-enterprise-gateway/* ../build/docker/kubernetes-enterprise-gateway
	cp ../dist/jupyter_enterprise_gateway* ../build/docker/kubernetes-enterprise-gateway
	@(cd ../build/docker/kubernetes-enterprise-gateway; docker build -t elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) . )
	@touch ../.image-kubernetes-enterprise-gateway
	@-docker images elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-image-kubernetes-kerneles: ../.image-kubernetes-kernels ## Build elyra/kubernetes-kernels:dev docker image
../.image-kubernetes-kernels: docker/kubernetes-kernels/*
	@make docker-clean-kubernetes-kernels
	@mkdir -p ../build/docker/kubernetes-kernels
	cp docker/kubernetes-kernels/* ../build/docker/kubernetes-kernels
	@(cd ../build/docker/kubernetes-kernels; docker build -t elyra/kubernetes-kernels:$(NB2KG_TAG) . )
	@touch ../.image-kubernetes-kernels
	@-docker images elyra/kubernetes-kernels:$(NB2KG_TAG)

docker-clean-kubernetes: docker-clean-kubernetes-enterprise-gateway  docker-clean-kubernetes-kerneles

docker-clean-kubernetes-enterprise-gateway: ## Remove elyra/kubernetes-enterprise-gateway:dev docker image
	@rm -f ../.image-kubernetes-enterprise-gateway
	@-docker rmi -f elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-clean-kubernetes-kerneles: ## Remove elyra/kubernetes-kerneles:dev docker image
	@rm -f ../.image-kubernetes-kerneles
	@-docker rmi -f elyra/kubernetes-kerneles:$(NB2KG_TAG)

##

docker-clean: docker-clean-enterprise-gateway docker-clean-nb2kg docker-clean-yarn-spark docker-clean-kubernetes-enterprise-gateway docker-clean-kubernetes-kernels## Remove docker images

