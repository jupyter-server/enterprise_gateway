# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs install sdist test release docker-clean docker-clean-enterprise-gateway docker-clean-nb2kg docker-clean-yarn-spark

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash
MAKEFILE_DIR:=${CURDIR}
VERSION:=0.7.0.dev0
WHEEL_FILE:=dist/jupyter_enterprise_gateway-$(VERSION)-py2.py3-none-any.whl
WHEEL_FILES:=$(shell find . -type f ! -path "./build/*" ! -path "./etc/*" ! -path "./docs/*" ! -path "./.git/*" ! -path "./.idea/*" ! -path "./dist/*" ! -path "./.image-enterprise-gateway" ! -path "./.image-nb2kg" ! -path "./.image-yarn-spark" )
KERNELSPECS_FILE:=dist/jupyter_enterprise_gateway_kernelspecs-$(VERSION).tar.gz
KERNELSPECS_FILES:=$(shell find etc/kernel* -type f -name '*')
ENTERPRISE_GATEWAY_TAG:=dev
NB2KG_TAG:=dev
YARN_SPARK_TAG:=2.1.0

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
	rm -f dist/enterprise_gateway_kernelspecs*.tar.gz
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

bdist: ## Make a dist/*.whl binary distribution
	make $(WHEEL_FILE)

$(WHEEL_FILE): $(WHEEL_FILES)
	$(SA) $(ENV) && python setup.py bdist_wheel $(POST_SDIST) \
		&& rm -rf *.egg-info

sdist: ## Make a dist/*.tar.gz source distribution
	$(SA) $(ENV) && python setup.py sdist $(POST_SDIST) \
		&& rm -rf *.egg-info

test: TEST?=
test: ## Run unit tests
ifeq ($(TEST),)
	$(SA) $(ENV) && nosetests
else
# e.g., make test TEST="test_gatewayapp.TestGatewayAppConfig"
	$(SA) $(ENV) && nosetests enterprise_gateway.tests.$(TEST)
endif

release: POST_SDIST=upload
release: bdist sdist ## Make a wheel + source release on PyPI


docker-images: docker-image-enterprise-gateway docker-image-nb2kg docker-image-yarn-spark ## Build docker images

docker-image-enterprise-gateway: docker-image-yarn-spark .image-enterprise-gateway ## Build elyra/enterprise-gateway:dev docker image
.image-enterprise-gateway: etc/docker/enterprise-gateway/* $(WHEEL_FILE) $(KERNELSPECS_FILE)
	@make docker-clean-enterprise-gateway bdist kernelspecs
	@mkdir -p build/docker/enterprise-gateway
	cp etc/docker/enterprise-gateway/* build/docker/enterprise-gateway
	cp dist/jupyter_enterprise_gateway* build/docker/enterprise-gateway
	@(cd build/docker/enterprise-gateway; docker build -t elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) . )
	@touch .image-enterprise-gateway
	@-docker images elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-image-nb2kg: .image-nb2kg ## Build elyra/nb2kg:dev docker image 
.image-nb2kg: etc/docker/nb2kg/* 
	@make docker-clean-nb2kg
	@mkdir -p build/docker/nb2kg
	cp etc/docker/nb2kg/* build/docker/nb2kg
	@(cd build/docker/nb2kg; docker build -t elyra/nb2kg:$(NB2KG_TAG) . )
	@touch .image-nb2kg
	@-docker images elyra/nb2kg:$(NB2KG_TAG)

docker-image-yarn-spark: .image-yarn-spark ## Build elyra/yarn-spark:2.1.0 docker image
.image-yarn-spark: etc/docker/yarn-spark/*
	@make docker-clean-yarn-spark
	@mkdir -p build/docker/yarn-spark
	cp etc/docker/yarn-spark/* build/docker/yarn-spark
	@(cd build/docker/yarn-spark; docker build -t elyra/yarn-spark:$(YARN_SPARK_TAG) . )
	@touch .image-yarn-spark
	@-docker images elyra/yarn-spark:$(YARN_SPARK_TAG)

docker-clean: docker-clean-enterprise-gateway docker-clean-nb2kg docker-clean-yarn-spark ## Remove docker images

docker-clean-enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
	@rm -f .image-enterprise-gateway
	@-docker rmi -f elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG)

docker-clean-nb2kg: ## Remove elyra/nb2kg:dev docker image
	@rm -f .image-nb2kg
	@-docker rmi -f elyra/nb2kg:$(NB2KG_TAG)

docker-clean-yarn-spark: ## Remove elyra/yarn-spark:2.1.0 docker image
	@rm -f .image-yarn-spark
	@-docker rmi -f elyra/yarn-spark:$(YARN_SPARK_TAG)

# itest should have these targets up to date: bdist kernelspecs docker-image-enterprise-gateway 

# itest configurable settings
# indicates which host (gateway or notebook) to connect to...
ITEST_HOST:=localhost:8888
# indicates the user to emulate.  This equates to 'KERNEL_USERNAME'...
ITEST_USER:=bob
# indicates the other set of options to use.  At this time, only the python notebooks succeed, so we're skipping R and Scala.
ITEST_OPTIONS=--notebook_files=../notebooks/Python_Client1.ipynb,../notebooks/Python_Cluster1.ipynb

# here's a complete example of the options (besides host and user) with their expected values ...
# ITEST_OPTIONS=--notebook_dir=<path-to-notebook-dir, default=../notebooks>  --notebook_files=<comma-separated-list-of-notebook-paths> \
# --target_kernels=<comma-separated-list-of-kernels> --continue_when_error=<boolean, default=True>

PREP_DOCKER:=1
itest: ## Run integration tests (optionally) against docker container
ifeq (1, $(PREP_DOCKER))
	make docker-prep
endif
	@rm -rf build/itests
	@mkdir -p build/itests
	@cp -r enterprise_gateway/itests build
	(cd build/itests/src/; $(SA) $(ENV); python main.py --host=$(ITEST_HOST) --username=$(ITEST_USER) $(ITEST_OPTIONS))
	@echo "Run \`docker logs itest\` to see enterprise-gateway log."

docker-prep: ## Prepare enterprise-gateway docker container for integration tests
	@-docker rm -f itest >> /dev/null
	@echo "Starting enterprise-gateway container (run \`docker logs itest\` to see container log)..."
	@-docker run -itd -p 8888:8888 -h itest --name itest elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) --elyra
	@(r="1"; while [ "$$r" == "1" ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; docker logs itest |grep 'Jupyter Enterprise Gateway at http'; r=$$?; done)
