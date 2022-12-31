# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help clean clean-images clean-enterprise-gateway clean-enterprise-gateway-demo clean-demo-base \
    clean-kernel-images clean-py clean-tf-py clean-tf-gpu-py clean-r clean-spark-r clean-scala toree-launcher \
    kernelspecs_all kernelspecs_yarn kernelspecs_conductor kernelspecs_kubernetes kernelspecs_docker clean-kernel-image-puller

SA?=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash
SUPPORTED_ARCHS=linux/arm64 linux/amd64
PLATFORM_ARCHS=`echo ${SUPPORTED_ARCHS} | sed "s/ /,/g"`

# Docker attributes - hub organization and tag.  Modify accordingly
HUB_ORG:=elyra

# Set NO_CACHE=--no-cache to force docker build to not use cached layers
NO_CACHE?=

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

clean: ## Make a clean source tree
	-rm -rf kernel-launchers/scala/lib
	-rm -rf kernel-launchers/scala/toree-launcher/project/project/

#
# Kernelspec build section *************************************************
#

KERNELSPECS := kernelspecs_all kernelspecs_yarn kernelspecs_conductor kernelspecs_kubernetes kernelspecs_docker
kernelspecs: $(KERNELSPECS) kernel_image_files

FILE_kernelspecs_all:=../dist/jupyter_enterprise_gateway_kernelspecs-$(VERSION).tar.gz
FILE_kernelspecs_yarn:=../dist/jupyter_enterprise_gateway_kernelspecs_yarn-$(VERSION).tar.gz
FILE_kernelspecs_conductor:=../dist/jupyter_enterprise_gateway_kernelspecs_conductor-$(VERSION).tar.gz
FILE_kernelspecs_kubernetes:=../dist/jupyter_enterprise_gateway_kernelspecs_kubernetes-$(VERSION).tar.gz
FILE_kernelspecs_docker:=../dist/jupyter_enterprise_gateway_kernelspecs_docker-$(VERSION).tar.gz

FILES_kernelspecs_all:=$(shell find kernel-launchers kernelspecs -type f -name '*')

TOREE_LAUNCHER_FILES:=$(shell find kernel-launchers/scala/toree-launcher/src -type f -name '*')

../build/kernelspecs: kernel-launchers/scala/lib  $(FILES_kernelspecs_all)
	@rm -rf ../build/kernelspecs
	@mkdir -p ../build/kernelspecs
		# Seed the build tree with initial files
	cp -r kernelspecs ../build
    # Distribute language and config-sensitive files.
    # On-prem kernelspecs get launcher files in the kernelspec hierarchy
	@echo ../build/kernelspecs/python_distributed | xargs -t -n 1 cp -r kernel-launchers/python/scripts
	@echo ../build/kernelspecs/dask_python_* | xargs -t -n 1 cp -r kernel-launchers/python/scripts
	@echo ../build/kernelspecs/spark_python_{conductor*,yarn*} | xargs -t -n 1 cp -r kernel-launchers/python/scripts
	@echo ../build/kernelspecs/spark_R_{conductor*,yarn*} | xargs -t -n 1 cp -r kernel-launchers/R/scripts
	@echo ../build/kernelspecs/spark_scala_{conductor*,yarn*} | xargs -t -n 1 cp -r kernel-launchers/scala/lib
	# Container-based kernelspecs (and operators) just get the container launchers
	@echo ../build/kernelspecs/{python,R,scala,python_tf,python_tf_gpu}_kubernetes | xargs -t -n 1 cp -r kernel-launchers/kubernetes/*
	@echo ../build/kernelspecs/spark_{python,R,scala}_kubernetes | xargs -t -n 1 cp -r kernel-launchers/kubernetes/*
	@echo ../build/kernelspecs/{python,R,scala,python_tf,python_tf_gpu}_docker | xargs -t -n 1 cp -r kernel-launchers/docker/*
	@echo ../build/kernelspecs/spark_python_operator | xargs -t -n 1 cp -r kernel-launchers/operators/*
        # Populate kernel resources.  Because tensorflow is also python, it should be last.
	@echo ../build/kernelspecs/*R* | xargs -t -n 1 cp -r kernel-resources/ir/*
	@echo ../build/kernelspecs/*scala* | xargs -t -n 1 cp -r kernel-resources/apache_toree/*
	@echo ../build/kernelspecs/*python* | xargs -t -n 1 cp -r kernel-resources/python/*
	@echo ../build/kernelspecs/*tf* | xargs -t -n 1 cp -r kernel-resources/tensorflow/*
    # Perform the copy again to enable local, per-kernel, overrides
	cp -r kernelspecs ../build
	@(cd ../build/kernelspecs; find . -name 'kernel.json' -print0 | xargs -0 sed -i.bak "s/VERSION/$(TAG)/g"; find . -name *.bak -print0 | xargs -0 rm -f)
	@mkdir -p ../dist

PATTERN_kernelspecs_all := *
PATTERN_kernelspecs_yarn := *_yarn_*
PATTERN_kernelspecs_conductor := *_conductor_*
PATTERN_kernelspecs_kubernetes := {*_kubernetes,*_operator}
PATTERN_kernelspecs_docker := *_docker

define BUILD_KERNELSPEC
$1: $$(FILE_$1)
$$(FILE_$1): ../build/kernelspecs
	rm -f $$(FILE_$1)
	@( cd ../build/kernelspecs; tar -pvczf "../$$(FILE_$1)" $$(PATTERN_$1) )
endef
$(foreach kernelspec,$(KERNELSPECS),$(eval $(call BUILD_KERNELSPEC,$(kernelspec))))

kernel-launchers/scala/lib: $(TOREE_LAUNCHER_FILES)
	-rm -rf kernel-launchers/scala/lib
	mkdir -p kernel-launchers/scala/lib
	@(cd kernel-launchers/scala/toree-launcher; sbt -Dversion=$(VERSION) -Dspark_version=$(SPARK_VERSION) package; cp target/scala-2.12/*.jar ../lib)
	curl -L https://repository.apache.org/content/repositories/releases/org/apache/toree/toree-assembly/0.5.0-incubating/toree-assembly-0.5.0-incubating.jar --output ./kernel-launchers/scala/lib/toree-assembly-0.5.0-incubating.jar

KERNEL_IMAGE_FILE:=../dist/jupyter_enterprise_gateway_kernel_image_files-$(VERSION).tar.gz
kernel_image_files: ../build/kernel_image_files
	rm -f $(KERNEL_IMAGE_FILE)
	@( cd ../build/kernel_image_files; tar -pvczf "../$(KERNEL_IMAGE_FILE)" . )

../build/kernel_image_files: kernel-launchers/scala/lib kernel-launchers/bootstrap/bootstrap-kernel.sh
	@rm -rf ../build/kernel_image_files
	@mkdir -p ../build/kernel_image_files/kernel-launchers
	cp kernel-launchers/bootstrap/* ../build/kernel_image_files
	cp -r kernel-launchers/{python,R,scala} ../build/kernel_image_files/kernel-launchers
	rm -rf ../build/kernel_image_files/kernel-launchers/scala/{\.*DS*,toree-launcher}  # leave only lib

#
# Docker image build section ***********************************************
#

KERNEL_IMAGES := kernel-py kernel-spark-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py
DOCKER_IMAGES := demo-base enterprise-gateway-demo enterprise-gateway kernel-image-puller $(KERNEL_IMAGES)
PUSHED_IMAGES := demo-base enterprise-gateway-demo enterprise-gateway kernel-image-puller $(KERNEL_IMAGES)

docker-images: $(DOCKER_IMAGES)
kernel-images: $(KERNEL_IMAGES)

push-images: push-enterprise-gateway-demo push-enterprise-gateway push-kernel-py push-kernel-spark-py push-kernel-tf-py push-kernel-r push-kernel-spark-r push-kernel-scala push-kernel-image-puller

clean-images: clean-enterprise-gateway-demo clean-demo-base clean-enterprise-gateway clean-kernel-image-puller clean-kernel-images
clean-kernel-images: clean-kernel-py clean-kernel-spark-py clean-kernel-tf-py clean-kernel-tf-gpu-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala

# Extra dependencies for each docker image...
DEPENDS_demo-base:
DEPENDS_enterprise-gateway-demo: $(FILE_kernelspecs_all)
DEPENDS_enterprise-gateway: $(FILE_kernelspecs_all)
DEPENDS_kernel-image-puller:
DEPENDS_kernel-py DEPENDS_kernel-spark-py DEPENDS_kernel-r DEPENDS_kernel-spark-r DEPENDS_kernel-scala DEPENDS_kernel-tf-py DEPENDS_kernel-tf-gpu-py: $(FILE_kernelspecs_kubernetes) $(FILE_kernelspecs_docker)

# Extra targets for each docker image...
TARGETS_demo-base:
TARGETS_kernel-image-puller:
TARGETS_enterprise-gateway TARGETS_enterprise-gateway-demo: kernelspecs
	@make -C .. bdist
TARGETS_kernel-py TARGETS_kernel-spark-py TARGETS_kernel-r TARGETS_kernel-spark-r TARGETS_kernel-scala TARGETS_kernel-tf-py TARGETS_kernel-tf-gpu-py: kernelspecs

# Extra files for each docker image...
FILES_demo-base :=
FILES_kernel-image-puller :=
FILES_enterprise-gateway-demo := ../dist/jupyter_enterprise_gateway_kernelspecs-* ../dist/jupyter_enterprise_gateway*.whl
FILES_enterprise-gateway := ../dist/jupyter_enterprise_gateway_kernel_image_files* ../dist/jupyter_enterprise_gateway_kernelspecs-* ../dist/jupyter_enterprise_gateway*.whl
FILES_kernel-py := ../dist/jupyter_enterprise_gateway_kernel_image_files*
FILES_kernel-spark-py := ../dist/jupyter_enterprise_gateway_kernel_image_files*
FILES_kernel-tf-py := ../dist/jupyter_enterprise_gateway_kernel_image_files*
FILES_kernel-tf-gpu-py := ../dist/jupyter_enterprise_gateway_kernel_image_files*
FILES_kernel-r := ../dist/jupyter_enterprise_gateway_kernel_image_files*
FILES_kernel-spark-r := ../dist/jupyter_enterprise_gateway_kernel_image_files*
FILES_kernel-scala := ../dist/jupyter_enterprise_gateway_kernel_image_files*

# Generate image creation targets for each entry in $(DOCKER_IMAGES).  Switch 'eval' to 'info' to see what is produced.
define BUILD_IMAGE
$1: ../.image-$1
../.image-$1: docker/$1/* DEPENDS_$1
	@make clean-$1 TARGETS_$1
	@mkdir -p ../build/docker/$1
	@cp -r docker/$1/* $$(FILES_$1) ../build/docker/$1
ifdef MULTIARCH_BUILD
	@echo "starting buildx builder for $1"
	-@(docker buildx rm $1)
	(docker buildx create --use --name $1)
	(cd ../build/docker/$1; docker buildx build ${NO_CACHE} --platform $(PLATFORM_ARCHS) --build-arg HUB_ORG=${HUB_ORG} --build-arg TAG=${TAG} --build-arg SPARK_VERSION=${SPARK_VERSION} -t $(HUB_ORG)/$1:$(TAG) . --push)
	@echo "remove builder instance $1"
	-(docker buildx rm $1)
else ifeq ($(TARGET_ARCH), $(filter $(TARGET_ARCH), $(SUPPORTED_ARCHS)))
	@echo "Building docker image for $(TARGET_ARCH)"
	(cd ../build/docker/$1; docker build ${NO_CACHE} --platform ${TARGET_ARCH} --build-arg HUB_ORG=${HUB_ORG} --build-arg TAG=${TAG} --build-arg SPARK_VERSION=${SPARK_VERSION} -t $(HUB_ORG)/$1:$(TAG) .)
	@-docker images $(HUB_ORG)/$1:$(TAG)
else
	@echo "TARGET_ARCH not defined or not in supported platforms: $(PLATFORM_ARCHS). Building docker image for default platform"
	(cd ../build/docker/$1; docker build ${NO_CACHE} --build-arg HUB_ORG=${HUB_ORG} --build-arg TAG=${TAG} --build-arg SPARK_VERSION=${SPARK_VERSION} -t $(HUB_ORG)/$1:$(TAG) .)
	@-docker images $(HUB_ORG)/$1:$(TAG)
endif
	@touch ../.image-$1
endef
$(foreach image,$(DOCKER_IMAGES),$(eval $(call BUILD_IMAGE,$(image))))

# Generate clean-xxx targets for each entry in $(DOCKER_IMAGES).  Switch 'eval' to 'info' to see what is produced.
define CLEAN_IMAGE
clean-$1:
	@rm -f ../.image-$1
	@-docker rmi -f $(HUB_ORG)/$1:$(TAG)
endef
$(foreach image,$(DOCKER_IMAGES),$(eval $(call CLEAN_IMAGE,$(image))))

# Publish each publish image on $(PUSHED_IMAGES) to DockerHub.  Switch 'eval' to 'info' to see what is produced.
define PUSH_IMAGE
push-$1:
	docker push $(HUB_ORG)/$1:$(TAG)
endef
$(foreach image,$(PUSHED_IMAGES),$(eval $(call PUSH_IMAGE,$(image))))
