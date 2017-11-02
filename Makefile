# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs install sdist test release docker_clean docker_clean_enterprise-gateway docker_clean_nb2kg docker_clean_hadoop-spark

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash
MAKEFILE_DIR:=${CURDIR}
VERSION:=0.7.0.dev0
WHEEL_FILE:=dist/jupyter_enterprise_gateway-$(VERSION)-py2.py3-none-any.whl
WHEEL_FILES:=$(shell find . -type f ! -path "./build/*" ! -path "./etc/*" ! -path "./docs/*" ! -path "./.git/*" ! -path "./.idea/*" ! -path "./dist/*" ! -path "./.image_enterprise-gateway" ! -path "./.image_nb2kg" ! -path "./.image_hadoop-spark" )
KERNELSPECS_FILE:=dist/jupyter_enterprise_gateway-kernelspecs-$(VERSION).tar.gz
KERNELSPECS_FILES:=$(shell find etc/kernel* -type f -name '*')
ENTERPRISE_GATEWAY_TAG:=dev
NB2KG_TAG:=dev
HADOOP_SPARK_TAG:=2.7.1-2.1.0

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

build:
env: ## Make a dev environment
	-conda create -y -n $(ENV) -c conda-forge --file requirements-conda.txt \
		--file requirements-test.txt
	$(SA) $(ENV) && \
		pip install -r requirements.txt && \
		pip install -r requirements-doc.txt && \
		pip install -e .

activate: ## eval `make activate`
	@echo "$(SA) $(ENV)"

clean: ## Make a clean source tree
	-rm -rf dist
	-rm -rf build
	-rm -rf *.egg-info
	-find enterprise_gateway -name __pycache__ -exec rm -fr {} \;
	-find enterprise_gateway -name '*.pyc' -exec rm -fr {} \;
	-$(SA) $(ENV) && make -C docs clean

nuke: ## Make clean + remove conda env
	-conda env remove -n $(ENV) -y

dev: ## Make a server in jupyter_websocket mode
	$(SA) $(ENV) && python enterprise_gateway

docs: ## Make HTML documentation
	$(SA) $(ENV) && make -C docs html

kernelspecs: $(KERNELSPECS_FILE) ## Make a tar.gz file consisting of kernelspec files

$(KERNELSPECS_FILE): $(KERNELSPECS_FILES)
	@mkdir -p build/kernelspecs
	cp -r etc/kernelspecs build
	@echo build/kernelspecs/*_python_* | xargs -t -n 1 cp -r etc/kernel-launchers/python/*
	@echo build/kernelspecs/*_R_* | xargs -t -n 1 cp -r etc/kernel-launchers/R/*
	@echo build/kernelspecs/*_scala_* | xargs -t -n 1 cp -r etc/kernel-launchers/scala/*
	@mkdir -p dist
	rm -f dist/enterprise_gateway-kernelspecs*.tar.gz
	@( cd build/kernelspecs; tar -pvczf "$(MAKEFILE_DIR)/$(KERNELSPECS_FILE)" * )

install: ## Make a conda env with dist/*.whl and dist/*.tar.gz installed
	-conda env remove -y -n $(ENV)-install
	conda create -y -n $(ENV)-install python=3 pip
	$(SA) $(ENV)-install && \
		pip install dist/*.whl && \
			jupyter enterprisegateway --help && \
			pip uninstall -y jupyter_enterprise_gateway
	conda env remove -y -n $(ENV)-install

	conda create -y -n $(ENV)-install python=3 pip
	$(SA) $(ENV)-install && \
		pip install dist/*.tar.gz && \
			jupyter enterprisegateway --help && \
			pip uninstall -y jupyter_enterprise_gateway
	conda env remove -y -n $(ENV)-install

bdist: $(WHEEL_FILE) ## Make a dist/*.whl binary distribution

$(WHEEL_FILE): $(WHEEL_FILES)
	$(SA) $(ENV) && python setup.py bdist_wheel $(POST_SDIST) \
		&& rm -rf *.egg-info

sdist: ## Make a dist/*.tar.gz source distribution
	$(SA) $(ENV) && python setup.py sdist $(POST_SDIST) \
		&& rm -rf *.egg-info

test: TEST?=
test: ## Make a python3 test run
ifeq ($(TEST),)
	$(SA) $(ENV) && nosetests
else
# e.g., make test TEST="test_gatewayapp.TestGatewayAppConfig"
	$(SA) $(ENV) && nosetests enterprise_gateway.tests.$(TEST)
endif

release: POST_SDIST=upload
release: bdist sdist ## Make a wheel + source release on PyPI


docker_images: docker_image_enterprise-gateway docker_image_nb2kg docker_image_hadoop-spark ## Build docker images

docker_image_enterprise-gateway: docker_image_hadoop-spark .image_enterprise-gateway ## Build elyra/enterprise-gateway:dev docker image
.image_enterprise-gateway: etc/docker/enterprise-gateway/* $(WHEEL_FILE) $(KERNELSPECS_FILE)
	@make bdist kernelspecs
	@mkdir -p build/docker/enterprise-gateway
	cp etc/docker/enterprise-gateway/* build/docker/enterprise-gateway
	cp dist/jupyter_enterprise_gateway* build/docker/enterprise-gateway
	@(cd build/docker/enterprise-gateway; docker build -t elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) . )
	@touch .image_enterprise-gateway
	@-docker images elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker_image_nb2kg: .image_nb2kg ## Build elyra/nb2kg:dev docker image 
.image_nb2kg: etc/docker/nb2kg/* 
	@mkdir -p build/docker/nb2kg
	cp etc/docker/nb2kg/* build/docker/nb2kg
	@(cd build/docker/nb2kg; docker build -t elyra/nb2kg:$(NB2KG_TAG) . )
	@touch .image_nb2kg
	@-docker images elyra/nb2kg:$(NB2KG_TAG)

docker_image_hadoop-spark: .image_hadoop-spark ## Build elyra/hadoop-spark:2.7.1-2.1.0 docker image
.image_hadoop-spark: etc/docker/hadoop-spark/* 
	@mkdir -p build/docker/hadoop-spark
	cp etc/docker/hadoop-spark/* build/docker/hadoop-spark
	@(cd build/docker/hadoop-spark; docker build -t elyra/hadoop-spark:$(HADOOP_SPARK_TAG) . )
	@touch .image_hadoop-spark
	@-docker images elyra/hadoop-spark:$(HADOOP_SPARK_TAG)

docker_clean: docker_clean_enterprise-gateway docker_clean_nb2kg docker_clean_hadoop-spark ## Remove docker images

docker_clean_enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
	@rm -f .image_enterprise-gateway
	@-docker rmi elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker_clean_nb2kg: ## Remove elyra/nb2kg:dev docker image
	@rm -f .image_nb2kg
	@-docker rmi elyra/nb2kg:$(NB2KG_TAG)

docker_clean_hadoop-spark: ## Remove elyra/hadoop-spark:2.7.0-2.1.0 docker image
	@rm -f .image_hadoop-spark
	@-docker rmi elyra/hadoop-spark:$(HADOOP_SPARK_TAG)

