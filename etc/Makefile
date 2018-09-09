# Copyright (c) Juper Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help clean clean-docker clean-enterprise-gateway clean-nb2kg clean-nb2kg-hub clean-yarn-spark \
    clean-kubernetes clean-py clean-tf-py clean-tf-gpu-py clean-r clean-scala toree-launcher

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash

KERNELSPECS_FILE:=../dist/jupyter_enterprise_gateway_kernelspecs-$(VERSION).tar.gz
KERNELSPECS_FILES:=$(shell find kernel-launchers kernelspecs -type f -name '*')
TOREE_LAUNCHER_FILES:=$(shell find kernel-launchers/scala/toree-launcher/src -type f -name '*')

# Docker attributes - hub organization and tag.  Modify accordingly
HUB_ORG:=elyra
TAG:=dev

NO_CACHE?=--no-cache

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

clean: ## Make a clean source tree
	-rm -rf kernel-launchers/scala/lib
	@(cd kernel-launchers/scala/toree-launcher; sbt $@)

#
# Kernelspec build section *************************************************
#

kernelspecs: $(KERNELSPECS_FILE) ## Make a tar.gz file consisting of kernelspec files

$(KERNELSPECS_FILE): $(KERNELSPECS_FILES) kernel-launchers/scala/lib  
	@mkdir -p ../build/kernelspecs
        # Seed the build tree with initial files
	cp -r kernelspecs ../build
        # Distribute language and config-sensitive files.
	@echo ../build/kernelspecs/{spark_,}python_* | xargs -t -n 1 cp -r kernel-launchers/python/*
	@echo ../build/kernelspecs/{spark_,}R_* | xargs -t -n 1 cp -r kernel-launchers/R/*
	@echo ../build/kernelspecs/{spark_,}scala_* | xargs -t -n 1 cp -r kernel-launchers/scala/lib
	@echo ../build/kernelspecs/{python,R,scala,python_tf,python_tf_gpu}_kubernetes | xargs -t -n 1 cp -r kernel-launchers/kubernetes/*
        # Perform the copy again to enable local, per-kernel, overrides
	cp -r kernelspecs ../build
	@mkdir -p ../dist
	rm -f $(KERNELSPECS_FILE)
	@( cd ../build/kernelspecs; tar -pvczf "../$(KERNELSPECS_FILE)" * )

kernel-launchers/scala/lib: $(TOREE_LAUNCHER_FILES)
	-rm -rf kernel-launchers/scala/lib
	mkdir -p kernel-launchers/scala/lib
	@(cd kernel-launchers/scala/toree-launcher; sbt -Dversion=$(VERSION) package; cp target/scala-2.11/*.jar ../lib)
	curl -L https://repository.apache.org/content/repositories/releases/org/apache/toree/toree-assembly/0.2.0-incubating/toree-assembly-0.2.0-incubating.jar --output ./kernel-launchers/scala/lib/toree-assembly-0.2.0-incubating.jar
	
#
# Docker image build section ***********************************************
#

DOCKER_IMAGES := enterprise-gateway-demo nb2kg nb2kg-hub yarn-spark
KUBERNETES_IMAGES = enterprise-gateway kernel-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py
IMAGES := $(DOCKER_IMAGES) $(KUBERNETES_IMAGES)

docker-images: $(DOCKER_IMAGES) $(KUBERNETES_IMAGES)
kubernetes-images: $(KUBERNETES_IMAGES)

kubernetes-publish: publish-enterprise-gateway publish-kernel-py publish-kernel-tf-py publish-kernel-tf-gpu-py publish-kernel-r publish-kernel-spark-r publish-kernel-scala

clean-images: clean-enterprise-gateway-demo clean-nb2kg clean-nb2kg-hub clean-yarn-spark clean-enterprise-gateway clean-kubernetes
clean-kubernetes: clean-enterprise-gateway clean-kernel-py clean-kernel-tf-py clean-kernel-tf-gpu-py clean-kernel-r clean-kernel-r clean-kernel-scala

# Extra dependencies for each docker image...
DEPENDS_nb2kg:
DEPENDS_nb2kg-hub:
DEPENDS_yarn-spark:
DEPENDS_enterprise-gateway-demo: yarn-spark
DEPENDS_enterprise-gateway: $(KERNELSPECS_FILE)
DEPENDS_kernel-py DEPENDS_kernel-r DEPENDS_kernel-spark-r DEPENDS_kernel-scala DEPENDS_kernel-tf-py DEPENDS_kernel-tf-gpu-py: $(KERNELSPECS_FILE)

# Extra targets for each docker image...
TARGETS_nb2kg:
TARGETS_nb2kg-hub:
TARGETS_yarn-spark:
TARGETS_enterprise-gateway-demo: kernelspecs
	@make -C .. bdist
	@-docker tag $(HUB_ORG)/yarn-spark:$(TAG) $(HUB_ORG)/yarn-spark:2.1.0
TARGETS_enterprise-gateway: kernelspecs
	@make -C .. bdist
TARGETS_kernel-py TARGETS_kernel-r TARGETS_kernel-spark-r TARGETS_kernel-scala TARGETS_kernel-tf-py TARGETS_kernel-tf-gpu-py: kernelspecs

# Extra files for each docker image...
FILES_nb2kg :=
FILES_nb2kg-hub :=
FILES_yarn-spark :=
FILES_enterprise-gateway-demo := ../dist/jupyter_enterprise_gateway*
FILES_kernel-py := ../dist/jupyter_enterprise_gateway_kernelspecs*
FILES_kernel-tf-py := ../dist/jupyter_enterprise_gateway_kernelspecs*
FILES_kernel-tf-gpu-py := ../dist/jupyter_enterprise_gateway_kernelspecs*
FILES_kernel-r := ../dist/jupyter_enterprise_gateway_kernelspecs*
FILES_kernel-spark-r := ../dist/jupyter_enterprise_gateway_kernelspecs*
FILES_kernel-scala := ../dist/jupyter_enterprise_gateway_kernelspecs*
FILES_enterprise-gateway := ../dist/jupyter_enterprise_gateway*

# Publish each publish image on $(IMAGES) to DockerHub.  Switch 'eval' to 'info' to see what is produced.
define PUBLISH_IMAGE
publish-$1:
	@docker push $(HUB_ORG)/$1:$(TAG)
endef
$(foreach image,$(IMAGES),$(eval $(call PUBLISH_IMAGE,$(image))))

# Generate image creation targets for each entry in $(IMAGES).  Switch 'eval' to 'info' to see what is produced.
define BUILD_IMAGE
$1: ../.image-$1
../.image-$1: docker/$1/* DEPENDS_$1
	@make clean-$1 TARGETS_$1
	@mkdir -p ../build/docker/$1
	cp docker/$1/* $$(FILES_$1) ../build/docker/$1
	@(cd ../build/docker/$1; docker build -t $(HUB_ORG)/$1:$(TAG) . )
	@touch ../.image-$1
	@-docker images $(HUB_ORG)/$1:$(TAG)
endef
$(foreach image,$(IMAGES),$(eval $(call BUILD_IMAGE,$(image))))


# Generate clean-xxx targets for each entry in $(IMAGES).  Switch 'eval' to 'info' to see what is produced.
define CLEAN_IMAGE
clean-$1:
	@rm -f ../.image-$1
	@-docker rmi -f $(HUB_ORG)/$1:$(TAG)
endef
$(foreach image,$(IMAGES),$(eval $(call CLEAN_IMAGE,$(image))))

