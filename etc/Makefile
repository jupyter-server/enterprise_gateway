# Copyright (c) Juper Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help clean clean-docker clean-docker-enterprise-gateway clean-docker-nb2kg clean-docker-yarn-spark \
    clean-kubernetes clean-kubernetes-py clean-kubernetes-r clean-kubernetes-scala toree-launcher

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash

KERNELSPECS_FILE:=../dist/jupyter_enterprise_gateway_kernelspecs-$(VERSION).tar.gz
KERNELSPECS_FILES:=$(shell find kernel-launchers kernelspecs -type f -name '*')
TOREE_LAUNCHER_FILES:=$(shell find kernel-launchers/scala/toree-launcher/src -type f -name '*')

ENTERPRISE_GATEWAY_TAG:=dev
KERNEL_TAG:=dev
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
	@echo ../build/kernelspecs/{spark_,}python_* | xargs -t -n 1 cp -r kernel-launchers/python/*
	@echo ../build/kernelspecs/{spark_,}R_* | xargs -t -n 1 cp -r kernel-launchers/R/*
	@echo ../build/kernelspecs/{spark_,}scala_* | xargs -t -n 1 cp -r kernel-launchers/scala/lib
	@echo ../build/kernelspecs/{python,R,scala}_kubernetes | xargs -t -n 1 cp -r kernel-launchers/kubernetes/*
	@mkdir -p ../dist
	rm -f $(KERNELSPECS_FILE)
	@( cd ../build/kernelspecs; tar -pvczf "../$(KERNELSPECS_FILE)" * )

kernel-launchers/scala/lib: $(TOREE_LAUNCHER_FILES)
	-rm -rf kernel-launchers/scala/lib
	mkdir -p kernel-launchers/scala/lib
	@(cd kernel-launchers/scala/toree-launcher; sbt -Dversion=$(VERSION) package; cp target/scala-2.11/*.jar ../lib)
	
docker-images: docker-enterprise-gateway docker-nb2kg docker-yarn-spark kubernetes-images ## Build docker images

test-parent:
	@echo wheel=../$(WHEEL_FILE)
	@make -C .. bdist 

docker-enterprise-gateway: docker-yarn-spark ../.image-enterprise-gateway ## Build elyra/enterprise-gateway:dev docker image
../.image-enterprise-gateway: docker/enterprise-gateway/* ../$(WHEEL_FILE) $(KERNELSPECS_FILE)
	@make clean-docker-enterprise-gateway kernelspecs
	@make -C .. bdist
	@mkdir -p ../build/docker/enterprise-gateway
	cp docker/enterprise-gateway/* ../build/docker/enterprise-gateway
	cp ../dist/jupyter_enterprise_gateway* ../build/docker/enterprise-gateway
	@(cd ../build/docker/enterprise-gateway; docker build $(NO_CACHE) -t elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) . )
	@touch ../.image-enterprise-gateway
	@-docker images elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-nb2kg: ../.image-nb2kg ## Build elyra/nb2kg:dev docker image 
../.image-nb2kg: docker/nb2kg/* 
	@make clean-docker-nb2kg
	@mkdir -p ../build/docker/nb2kg
	cp docker/nb2kg/* ../build/docker/nb2kg
	@(cd ../build/docker/nb2kg; docker build $(NO_CACHE) -t elyra/nb2kg:$(NB2KG_TAG) . )
	@touch ../.image-nb2kg
	@-docker images elyra/nb2kg:$(NB2KG_TAG)

docker-yarn-spark: ../.image-yarn-spark ## Build elyra/yarn-spark:2.1.0 docker image
../.image-yarn-spark: docker/yarn-spark/*
	@make clean-docker-yarn-spark
	@mkdir -p ../build/docker/yarn-spark
	cp docker/yarn-spark/* ../build/docker/yarn-spark
	@(cd ../build/docker/yarn-spark; docker build $(NO_CACHE) -t elyra/yarn-spark:$(YARN_SPARK_TAG) . )
	@touch ../.image-yarn-spark
	@-docker images elyra/yarn-spark:$(YARN_SPARK_TAG)

clean-docker-enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
	@rm -f ../.image-enterprise-gateway
	@-docker rmi -f elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

clean-docker-nb2kg: ## Remove elyra/nb2kg:dev docker image
	@rm -f ../.image-nb2kg
	@-docker rmi -f elyra/nb2kg:$(NB2KG_TAG)

clean-docker-yarn-spark: ## Remove elyra/yarn-spark:2.1.0 docker image
	@rm -f ../.image-yarn-spark
	@-docker rmi -f elyra/yarn-spark:$(YARN_SPARK_TAG)

## Kubernetes container images

kubernetes-images: kubernetes-enterprise-gateway kubernetes-kernel-py kubernetes-kernel-r kubernetes-kernel-scala

kubernetes-enterprise-gateway: ../.image-kubernetes-enterprise-gateway ## Build elyra/kubernetes-enterprise-gateway:dev docker image
../.image-kubernetes-enterprise-gateway: docker/kubernetes-enterprise-gateway/* ../$(WHEEL_FILE) $(KERNELSPECS_FILE)
	@make clean-kubernetes-enterprise-gateway
	@make -C .. bdist
	@make -C .. kernelspecs
	@mkdir -p ../build/docker/kubernetes-enterprise-gateway
	cp docker/kubernetes-enterprise-gateway/* ../build/docker/kubernetes-enterprise-gateway
	cp ../dist/jupyter_enterprise_gateway* ../build/docker/kubernetes-enterprise-gateway
	@(cd ../build/docker/kubernetes-enterprise-gateway; docker build -t elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) . )
	@touch ../.image-kubernetes-enterprise-gateway
	@-docker images elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

# FIXME - build functions for these that take the image name or language suffix
kubernetes-kernel-py: ../.image-kubernetes-kernel-py ## Build elyra/kubernetes-kernel-py:dev docker image
../.image-kubernetes-kernel-py: docker/kubernetes-kernel-py/* $(KERNELSPECS_FILE)
	@make clean-kubernetes-kernel-py
	@make -C .. kernelspecs
	@mkdir -p ../build/docker/kubernetes-kernel-py
	cp docker/kubernetes-kernel-py/* ../build/docker/kubernetes-kernel-py
	cp ../dist/jupyter_enterprise_gateway_kernelspecs* ../build/docker/kubernetes-kernel-py
	@(cd ../build/docker/kubernetes-kernel-py; docker build -t elyra/kubernetes-kernel-py:$(KERNEL_TAG) . )
	@touch ../.image-kubernetes-kernel-py
	@-docker images elyra/kubernetes-kernel-py:$(KERNEL_TAG)

kubernetes-kernel-r: ../.image-kubernetes-kernel-r ## Build elyra/kubernetes-kernel-r:dev docker image
../.image-kubernetes-kernel-r: docker/kubernetes-kernel-r/* $(KERNELSPECS_FILE)
	@make clean-kubernetes-kernel-r
	@make -C .. kernelspecs
	@mkdir -p ../build/docker/kubernetes-kernel-r
	cp docker/kubernetes-kernel-r/* ../build/docker/kubernetes-kernel-r
	cp ../dist/jupyter_enterprise_gateway_kernelspecs* ../build/docker/kubernetes-kernel-r
	@(cd ../build/docker/kubernetes-kernel-r; docker build -t elyra/kubernetes-kernel-r:$(KERNEL_TAG) . )
	@touch ../.image-kubernetes-kernel-r
	@-docker images elyra/kubernetes-kernel-r:$(KERNEL_TAG)

kubernetes-kernel-scala: ../.image-kubernetes-kernel-scala ## Build elyra/kubernetes-kernel-scala:dev docker image
../.image-kubernetes-kernel-scala: docker/kubernetes-kernel-scala/* $(KERNELSPECS_FILE)
	@make clean-kubernetes-kernel-scala
	@make -C .. kernelspecs
	@mkdir -p ../build/docker/kubernetes-kernel-scala
	cp docker/kubernetes-kernel-scala/* ../build/docker/kubernetes-kernel-scala
	cp ../dist/jupyter_enterprise_gateway_kernelspecs* ../build/docker/kubernetes-kernel-scala
	@(cd ../build/docker/kubernetes-kernel-scala; docker build -t elyra/kubernetes-kernel-scala:$(KERNEL_TAG) . )
	@touch ../.image-kubernetes-kernel-scala
	@-docker images elyra/kubernetes-kernel-scala:$(KERNEL_TAG)

clean-kubernetes: clean-kubernetes-enterprise-gateway clean-kubernetes-kernel-py clean-kubernetes-kernel-r clean-kubernetes-kernel-scala

# FIXME - build functions for these that take the image name 
clean-kubernetes-enterprise-gateway: ## Remove elyra/kubernetes-enterprise-gateway:dev docker image
	@rm -f ../.image-kubernetes-enterprise-gateway
	@-docker rmi -f elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)_x
	@-docker tag elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)_x
	@-docker rmi -f elyra/kubernetes-enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

clean-kubernetes-kernel-py: ## Remove elyra/kubernetes-kernel-py:dev docker image
	@rm -f ../.image-kubernetes-kernel-py
	@-docker rmi -f elyra/kubernetes-kernel-py:$(KERNEL_TAG)_x
	@-docker tag elyra/kubernetes-kernel-py:$(KERNEL_TAG) elyra/kubernetes-kernel-py:$(KERNEL_TAG)_x
	@-docker rmi -f elyra/kubernetes-kernel-py:$(KERNEL_TAG)

clean-kubernetes-kernel-r: ## Remove elyra/kubernetes-kernel-r:dev docker image
	@rm -f ../.image-kubernetes-kernel-r
	@-docker rmi -f elyra/kubernetes-kernel-r:$(KERNEL_TAG)_x
	@-docker tag elyra/kubernetes-kernel-r:$(KERNEL_TAG) elyra/kubernetes-kernel-r:$(KERNEL_TAG)_x
	@-docker rmi -f elyra/kubernetes-kernel-r:$(KERNEL_TAG)

clean-kubernetes-kernel-scala: ## Remove elyra/kubernetes-kernel-scala:dev docker image
	@rm -f ../.image-kubernetes-kernel-scala
	@-docker rmi -f elyra/kubernetes-kernel-scala:$(KERNEL_TAG)_x
	@-docker tag elyra/kubernetes-kernel-scala:$(KERNEL_TAG) elyra/kubernetes-kernel-scala:$(KERNEL_TAG)_x
	@-docker rmi -f elyra/kubernetes-kernel-scala:$(KERNEL_TAG)
##

clean-docker: clean-docker-enterprise-gateway clean-docker-nb2kg clean-docker-yarn-spark clean-kubernetes-enterprise-gateway clean-kubernetes ## Remove docker images

