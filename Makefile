# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs install sdist test release clean-images clean-enterprise-gateway \
    clean-nb2kg clean-yarn-spark clean-kernel-images clean-enterprise-gateway \
    clean-kernel-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py \
    clean-kernel-tf-gpu-py publish-images

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash

VERSION:=2.0.0.dev0

WHEEL_FILE:=dist/jupyter_enterprise_gateway-$(VERSION)-py2.py3-none-any.whl
WHEEL_FILES:=$(shell find . -type f ! -path "./build/*" ! -path "./etc/*" ! -path "./docs/*" ! -path "./.git/*" ! -path "./.idea/*" ! -path "./dist/*" ! -path "./.image-*" )

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

build:
env: ## Make a dev environment
	-conda env create --file requirements.yml --name $(ENV)

activate: ## eval `make activate`
	@echo "$(SA) $(ENV)"

clean: ## Make a clean source tree
	-rm -rf dist
	-rm -rf build
	-rm -rf *.egg-info
	-find enterprise_gateway -name __pycache__ -exec rm -fr {} \;
	-find enterprise_gateway -name '*.pyc' -exec rm -fr {} \;
	-$(SA) $(ENV) && make -C docs clean
	-$(SA) $(ENV) && make -C etc clean

nuke: ## Make clean + remove conda env
	-conda env remove -n $(ENV) -y

dev: ## Make a server in jupyter_websocket mode
	$(SA) $(ENV) && python enterprise_gateway

docs: ## Make HTML documentation
	$(SA) $(ENV) && make -C docs html

kernelspecs: ## Create an archive with sample kernelspecs
	make VERSION=$(VERSION) -C  etc $@

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

bdist:
	make $(WHEEL_FILE)

$(WHEEL_FILE): $(WHEEL_FILES)
	$(SA) $(ENV) && python setup.py bdist_wheel $(POST_SDIST) \
		&& rm -rf *.egg-info

sdist:
	$(SA) $(ENV) && python setup.py sdist $(POST_SDIST) \
		&& rm -rf *.egg-info

dist: bdist sdist kernelspecs ## Make source, binary and kernelspecs distribution to dist folder

test: TEST?=
test: ## Run unit tests
ifeq ($(TEST),)
	$(SA) $(ENV) && nosetests -v enterprise_gateway.tests
else
# e.g., make test TEST="test_gatewayapp.TestGatewayAppConfig"
	$(SA) $(ENV) && nosetests -v enterprise_gateway.tests.$(TEST)
endif

release: POST_SDIST=upload
release: bdist sdist ## Make a wheel + source release on PyPI

# Here for doc purposes
docker-images:  ## Build docker images
enterprise-gateway-demo:  ## Build elyra/enterprise-gateway-demo:dev docker image
yarn-spark:  ## Build elyra/yarn-spark:2.3.1 docker image
nb2kg:  ## Build elyra/nb2kg:dev docker image
enterprise-gateway: ## Build elyra/enterprise-gateway:dev docker image
kernel-images: ## Build kernel-based docker images
kernel-py: ## Build elyra/kernel-py:dev docker image
kernel-r: ## Build elyra/kernel-r:dev docker image
kernel-spark-r: ## Build elyra/kernel-spark-r:dev docker image
kernel-scala: ## Build elyra/kernel-scala:dev docker image
kernel-tf-py: ## Build elyra/kernel-tf-py:dev docker image
kernel-tf-gpu-py: ## Build elyra/kernel-tf-gpu-py:dev docker image

# Actual working targets...
docker-images enterprise-gateway-demo yarn-spark nb2kg kernel-images enterprise-gateway kernel-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

# Here for doc purposes
clean-images: ## Remove docker images
clean-enterprise-gateway-demo: ## Remove elyra/enterprise-gateway-demo:dev docker image
clean-nb2kg: ## Remove elyra/nb2kg:dev docker image
clean-yarn-spark: ## Remove elyra/yarn-spark:2.3.1 docker image
clean-enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
clean-kernel-images: ## Remove kernel-based docker images
clean-kernel-py: ## Remove elyra/kernel-py:dev docker image
clean-kernel-r: ## Remove elyra/kernel-r:dev docker image
clean-kernel-spark-r: ## Remove elyra/kernel-spark-r:dev docker image
clean-kernel-scala: ## Remove elyra/kernel-scala:dev docker image
clean-kernel-tf-py: ## Remove elyra/kernel-tf-py:dev docker image
clean-kernel-tf-gpu-py: ## Remove elyra/kernel-tf-gpu-py:dev docker image

clean-images clean-enterprise-gateway-demo clean-nb2kg clean-yarn-spark clean-kernel-images clean-enterprise-gateway clean-kernel-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py clean-kernel-tf-gpu-py:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

publish-images: ## Push docker images to docker hub
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

ENTERPRISE_GATEWAY_TAG?=dev

# itest should have these targets up to date: bdist kernelspecs docker-enterprise-gateway

itest: itest-docker itest-yarn

# itest configurable settings
# indicates two things:
# this prefix is used by itest to determine hostname to test against, in addtion,
# if itests will be run locally with docker-prep target, this will set the hostname within that container as well
ITEST_HOSTNAME_PREFIX?=itest

# indicates the user to emulate.  This equates to 'KERNEL_USERNAME'...
ITEST_USER?=bob
# indicates the other set of options to use.  At this time, only the python notebooks succeed, so we're skipping R and Scala.
ITEST_OPTIONS?=

# here's an example of the options (besides host and user) with their expected values ...
# ITEST_OPTIONS=--impersonation < True | False >

ITEST_YARN_PORT?=8888
ITEST_YARN_HOST?=localhost:$(ITEST_YARN_PORT)
ITEST_YARN_TESTS?=enterprise_gateway.itests

PREP_ITEST_YARN?=1
itest-yarn: ## Run integration tests (optionally) against docker demo (YARN) container
ifeq (1, $(PREP_ITEST_YARN))
	make itest-yarn-prep
endif
	($(SA) $(ENV) && GATEWAY_HOST=$(ITEST_YARN_HOST) KERNEL_USERNAME=$(ITEST_USER) ITEST_HOSTNAME_PREFIX=$(ITEST_HOSTNAME_PREFIX) nosetests -v $(ITEST_YARN_TESTS))
	@echo "Run \`docker logs itest-yarn\` to see enterprise-gateway log."

PREP_TIMEOUT?=60
itest-yarn-prep:
	@-docker rm -f itest-yarn >> /dev/null
	@echo "Starting enterprise-gateway container (run \`docker logs itest-yarn\` to see container log)..."
	@-docker run -itd -p $(ITEST_YARN_PORT):$(ITEST_YARN_PORT) -h itest-yarn --name itest-yarn -v `pwd`/enterprise_gateway/itests:/tmp/byok elyra/enterprise-gateway-demo:$(ENTERPRISE_GATEWAY_TAG) --elyra
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt $(PREP_TIMEOUT) ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker logs itest-yarn |grep --regexp "Jupyter Enterprise Gateway .* is available at http"; r=$$?; done; if [ $$attempts -ge $(PREP_TIMEOUT) ]; then echo "Wait for startup timed out!"; exit 1; fi;)


# This should get cleaned up once docker support is more mature
ITEST_DOCKER_PORT?=8889
ITEST_DOCKER_HOST?=localhost:$(ITEST_DOCKER_PORT)
ITEST_DOCKER_TESTS?=enterprise_gateway.itests.test_r_kernel.TestRKernelLocal enterprise_gateway.itests.test_python_kernel.TestPythonKernelLocal enterprise_gateway.itests.test_scala_kernel.TestScalaKernelLocal
ITEST_DOCKER_KERNELS=PYTHON_KERNEL_LOCAL_NAME=python_docker SCALA_KERNEL_LOCAL_NAME=scala_docker R_KERNEL_LOCAL_NAME=R_docker

PREP_ITEST_DOCKER?=1
itest-docker: ## Run integration tests (optionally) against docker swarm
ifeq (1, $(PREP_ITEST_DOCKER))
	make itest-docker-prep
endif
	($(SA) $(ENV) && GATEWAY_HOST=$(ITEST_DOCKER_HOST) KERNEL_USERNAME=$(ITEST_USER) $(ITEST_DOCKER_KERNELS) nosetests -v $(ITEST_DOCKER_TESTS))
	@echo "Run \`docker service logs itest-docker\` to see enterprise-gateway log."

PREP_TIMEOUT?=60
itest-docker-prep:
	@-docker service rm itest-docker
	# Check if swarm mode is active, if not attempt to create the swarm
	@(docker info | grep -q 'Swarm: active'; if [ $$? -eq 1 ]; then docker swarm init; fi;)
	@echo "Starting enterprise-gateway swarm service (run \`docker service logs itest-docker\` to see service log)..."
	@KG_PORT=${ITEST_DOCKER_PORT} EG_NAME=itest-docker etc/docker/enterprise-gateway-swarm.sh
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt $(PREP_TIMEOUT) ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker service logs itest-docker |grep --regexp "Jupyter Enterprise Gateway .* is available at http"; r=$$?; done; if [ $$attempts -ge $(PREP_TIMEOUT) ]; then echo "Wait for startup timed out!"; exit 1; fi;)
