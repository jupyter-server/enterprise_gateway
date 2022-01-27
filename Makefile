# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs install sdist test release clean-images clean-enterprise-gateway \
    clean-demo-base clean-kernel-images clean-enterprise-gateway \
    clean-kernel-py clean-kernel-spark-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py \
    clean-kernel-tf-gpu-py clean-kernel-image-puller push-images push-enterprise-gateway-demo push-demo-base \
    push-kernel-images push-enterprise-gateway push-kernel-py push-kernel-spark-py push-kernel-r push-kernel-spark-r \
    push-kernel-scala push-kernel-tf-py push-kernel-tf-gpu-py push-kernel-image-puller publish helm-chart

SA?=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash

VERSION?=2.6.0
SPARK_VERSION?=2.4.6

ifeq (dev, $(findstring dev, $(VERSION)))
    TAG:=dev
else
    TAG:=$(VERSION)
endif


WHEEL_FILE:=dist/jupyter_enterprise_gateway-$(VERSION)-py2.py3-none-any.whl
WHEEL_FILES:=$(shell find . -type f ! -path "./build/*" ! -path "./etc/*" ! -path "./docs/*" ! -path "./.git/*" ! -path "./.idea/*" ! -path "./dist/*" ! -path "./.image-*" )

HELM_CHART:=dist/jupyter_enterprise_gateway_helm-$(VERSION).tgz
HELM_CHART_FILES:=$(shell find etc/kubernetes/helm -type f)

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

build:
env: ## Make a dev environment
	-conda env create --file requirements.yml --name $(ENV)
	-conda env config vars set PYTHONPATH=$(PWD) --name $(ENV)

activate: ## Print instructions to activate the virtualenv (default: enterprise-gateway-dev)
	@echo "Run \`$(SA) $(ENV)\` to activate the environment."

clean: ## Make a clean source tree
	-rm -rf dist
	-rm -rf build
	-rm -rf *.egg-info
	-find . -name target -type d -exec rm -fr {} +
	-find . -name __pycache__  -type d -exec rm -fr {} +
	-find enterprise_gateway -name '*.pyc' -exec rm -fr {} +
	-find website -name '.sass-cache' -type d -exec rm -fr {} +
	-find website -name '_site' -type d -exec rm -fr {} +
	-find website -name 'build' -type d -exec rm -fr {} +
	-$(SA) $(ENV) && make -C docs clean
	-$(SA) $(ENV) && make -C etc clean

lint: ## Check code style
	$(SA) $(ENV) && flake8 enterprise_gateway

nuke: ## Make clean + remove conda env
	-conda env remove -n $(ENV) -y

dev: ## Make a server in jupyter_websocket mode
	$(SA) $(ENV) && python enterprise_gateway

docs: ## Make HTML documentation
	$(SA) $(ENV) && make -C docs html

kernelspecs:  kernelspecs_all kernelspecs_yarn kernelspecs_conductor kernelspecs_kubernetes kernelspecs_docker kernel_image_files ## Create archives with sample kernelspecs
kernelspecs_all kernelspecs_yarn kernelspecs_conductor kernelspecs_kubernetes kernelspecs_docker kernel_image_files:
	make VERSION=$(VERSION) TAG=$(TAG) SPARK_VERSION=$(SPARK_VERSION) -C  etc $@

install: ## Make a conda env with dist/jupyter_enterprise_gateway-*.whl and dist/jupyter_enterprise_gateway-*.tar.gz installed
	-conda env remove -y -n $(ENV)-install
	conda create -y -n $(ENV)-install python=3 pip
	$(SA) $(ENV)-install && \
		pip install dist/jupyter_enterprise_gateway-*.whl && \
			jupyter enterprisegateway --help && \
			pip uninstall -y jupyter_enterprise_gateway
	conda env remove -y -n $(ENV)-install

	conda create -y -n $(ENV)-install python=3 pip
	$(SA) $(ENV)-install && \
		pip install dist/jupyter_enterprise_gateway-*.tar.gz && \
			jupyter enterprisegateway --help && \
			pip uninstall -y jupyter_enterprise_gateway
	conda env remove -y -n $(ENV)-install

bdist: lint
	make $(WHEEL_FILE)

$(WHEEL_FILE): $(WHEEL_FILES)
	$(SA) $(ENV) && python setup.py bdist_wheel $(POST_SDIST) \
		&& rm -rf *.egg-info

sdist:
	$(SA) $(ENV) && python setup.py sdist $(POST_SDIST) \
		&& rm -rf *.egg-info

helm-chart: ## Make helm chart distribution
	make $(HELM_CHART)

$(HELM_CHART): $(HELM_CHART_FILES)
	(mkdir -p dist; cd etc/kubernetes/helm; tar -cvzf ../../../$(HELM_CHART) enterprise-gateway)

dist: lint bdist sdist kernelspecs helm-chart ## Make source, binary, kernelspecs and helm chart distributions to dist folder

TEST_DEBUG_OPTS:=

test-debug:
	make TEST_DEBUG_OPTS="--nocapture --nologcapture --logging-level=10" test

test: TEST?=
test: ## Run unit tests
ifeq ($(TEST),)
	$(SA) $(ENV) && pytest -v -s $(TEST_DEBUG_OPTS) enterprise_gateway/tests
else
# e.g., make test TEST="test_gatewayapp.TestGatewayAppConfig"
	$(SA) $(ENV) && pytest -v -s $(TEST_DEBUG_OPTS) enterprise_gateway/tests/$(TEST)
endif

release: POST_SDIST=upload
release: bdist sdist ## Make a wheel + source release on PyPI

# Here for doc purposes
docker-images:  ## Build docker images (includes kernel-based images)
kernel-images: ## Build kernel-based docker images

# Actual working targets...
docker-images: demo-base enterprise-gateway-demo kernel-images enterprise-gateway kernel-py kernel-spark-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py kernel-image-puller

enterprise-gateway-demo kernel-images enterprise-gateway kernel-py kernel-spark-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py kernel-image-puller:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) NO_CACHE=$(NO_CACHE) TAG=$(TAG) SPARK_VERSION=$(SPARK_VERSION) -C etc $@

demo-base:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) NO_CACHE=$(NO_CACHE) TAG=$(SPARK_VERSION) SPARK_VERSION=$(SPARK_VERSION) -C etc $@

# Here for doc purposes
clean-images: clean-demo-base ## Remove docker images (includes kernel-based images)
clean-kernel-images: ## Remove kernel-based images

clean-images clean-enterprise-gateway-demo clean-kernel-images clean-enterprise-gateway clean-kernel-py clean-kernel-spark-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py clean-kernel-tf-gpu-py clean-kernel-image-puller:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) TAG=$(TAG) -C etc $@

clean-demo-base:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) TAG=$(SPARK_VERSION) -C etc $@

push-images: push-demo-base
push-images push-enterprise-gateway-demo push-kernel-images push-enterprise-gateway push-kernel-py push-kernel-spark-py push-kernel-r push-kernel-spark-r push-kernel-scala push-kernel-tf-py push-kernel-tf-gpu-py push-kernel-image-puller:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) TAG=$(TAG) -C etc $@

push-demo-base:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) TAG=$(SPARK_VERSION) -C etc $@

publish: NO_CACHE=--no-cache
publish: clean clean-images dist docker-images push-images

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
ITEST_YARN_TESTS?=enterprise_gateway/itests

ITEST_KERNEL_LAUNCH_TIMEOUT=120

LOG_LEVEL=INFO

itest-yarn-debug: ## Run integration tests (optionally) against docker demo (YARN) container with print statements
	make LOG_LEVEL=DEBUG TEST_DEBUG_OPTS="--log-level=10" itest-yarn

PREP_ITEST_YARN?=1
itest-yarn: ## Run integration tests (optionally) against docker demo (YARN) container
ifeq (1, $(PREP_ITEST_YARN))
	make itest-yarn-prep
endif
	($(SA) $(ENV) && GATEWAY_HOST=$(ITEST_YARN_HOST) LOG_LEVEL=$(LOG_LEVEL) KERNEL_USERNAME=$(ITEST_USER) KERNEL_LAUNCH_TIMEOUT=$(ITEST_KERNEL_LAUNCH_TIMEOUT) SPARK_VERSION=$(SPARK_VERSION) ITEST_HOSTNAME_PREFIX=$(ITEST_HOSTNAME_PREFIX) pytest -v -s $(TEST_DEBUG_OPTS) $(ITEST_YARN_TESTS))
	@echo "Run \`docker logs itest-yarn\` to see enterprise-gateway log."

PREP_TIMEOUT?=60
itest-yarn-prep:
	@-docker rm -f itest-yarn >> /dev/null
	@echo "Starting enterprise-gateway container (run \`docker logs itest-yarn\` to see container log)..."
	@-docker run -itd -p $(ITEST_YARN_PORT):$(ITEST_YARN_PORT) -p 8088:8088 -p 8042:8042 -h itest-yarn --name itest-yarn -v `pwd`/enterprise_gateway/itests:/tmp/byok elyra/enterprise-gateway-demo:$(TAG) --gateway
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt $(PREP_TIMEOUT) ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker logs itest-yarn |grep --regexp "Jupyter Enterprise Gateway .* is available at http"; r=$$?; done; if [ $$attempts -ge $(PREP_TIMEOUT) ]; then echo "Wait for startup timed out!"; exit 1; fi;)


# This should get cleaned up once docker support is more mature
ITEST_DOCKER_PORT?=8889
ITEST_DOCKER_HOST?=localhost:$(ITEST_DOCKER_PORT)
ITEST_DOCKER_TESTS?=enterprise_gateway/itests/test_r_kernel.py::TestRKernelLocal enterprise_gateway/itests/test_python_kernel.py::TestPythonKernelLocal enterprise_gateway/itests/test_scala_kernel.py::TestScalaKernelLocal
ITEST_DOCKER_KERNELS=PYTHON_KERNEL_LOCAL_NAME=python_docker SCALA_KERNEL_LOCAL_NAME=scala_docker R_KERNEL_LOCAL_NAME=R_docker

itest-docker-debug: ## Run integration tests (optionally) against docker container with print statements
	make LOG_LEVEL=DEBUG TEST_DEBUG_OPTS="--nocapture --nologcapture --logging-level=10" itest-docker

PREP_ITEST_DOCKER?=1
itest-docker: ## Run integration tests (optionally) against docker swarm
ifeq (1, $(PREP_ITEST_DOCKER))
	make itest-docker-prep
endif
	($(SA) $(ENV) && GATEWAY_HOST=$(ITEST_DOCKER_HOST) LOG_LEVEL=$(LOG_LEVEL) KERNEL_USERNAME=$(ITEST_USER) KERNEL_LAUNCH_TIMEOUT=$(ITEST_KERNEL_LAUNCH_TIMEOUT) $(ITEST_DOCKER_KERNELS) ITEST_HOSTNAME_PREFIX=$(ITEST_USER) pytest -v -s $(TEST_DEBUG_OPTS) $(ITEST_DOCKER_TESTS))
	@echo "Run \`docker service logs itest-docker\` to see enterprise-gateway log."

PREP_TIMEOUT?=60
itest-docker-prep:
	@-docker service rm enterprise-gateway_enterprise-gateway enterprise-gateway_enterprise-gateway-proxy
	@-docker swarm leave --force
	# Check if swarm mode is active, if not attempt to create the swarm
	@(docker info | grep -q 'Swarm: active'; if [ $$? -eq 1 ]; then docker swarm init; fi;)
	@echo "Starting enterprise-gateway swarm service (run \`docker service logs enterprise-gateway_enterprise-gateway\` to see service log)..."
	@KG_PORT=${ITEST_DOCKER_PORT} EG_DOCKER_NETWORK=enterprise-gateway docker stack deploy -c etc/docker/docker-compose.yml enterprise-gateway
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt $(PREP_TIMEOUT) ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker service logs enterprise-gateway_enterprise-gateway 2>&1 |grep --regexp "Jupyter Enterprise Gateway .* is available at http"; r=$$?; done; if [ $$attempts -ge $(PREP_TIMEOUT) ]; then echo "Wait for startup timed out!"; exit 1; fi;)
