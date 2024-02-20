# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help clean clean-env dev dev-http docs install bdist sdist test release check_dists \
    clean-images clean-enterprise-gateway clean-demo-base clean-kernel-images clean-enterprise-gateway \
    clean-kernel-py clean-kernel-spark-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py \
    clean-kernel-tf-gpu-py clean-kernel-image-puller push-images push-enterprise-gateway-demo push-demo-base \
    push-kernel-images push-enterprise-gateway push-kernel-py push-kernel-spark-py push-kernel-r push-kernel-spark-r \
    push-kernel-scala push-kernel-tf-py push-kernel-tf-gpu-py push-kernel-image-puller publish helm-chart

SA?=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash
MULTIARCH_BUILD?=
TARGET_ARCH?=undefined

VERSION?=3.3.0.dev0
SPARK_VERSION?=3.2.1

ifeq (dev, $(findstring dev, $(VERSION)))
    TAG:=dev
else
    TAG:=$(VERSION)
endif


WHEEL_FILES:=$(shell find . -type f ! -path "./build/*" ! -path "./etc/*" ! -path "./docs/*" ! -path "./.git/*" ! -path "./.idea/*" ! -path "./dist/*" ! -path "./.image-*" ! -path "*/__pycache__/*" )
WHEEL_FILE:=dist/jupyter_enterprise_gateway-$(VERSION)-py3-none-any.whl
SDIST_FILE:=dist/jupyter_enterprise_gateway-$(VERSION).tar.gz
DIST_FILES=$(WHEEL_FILE) $(SDIST_FILE)

HELM_DESIRED_VERSION:=v3.8.2  # Pin the version of helm to use (v3.8.2 is latest as of 4/21/22)
HELM_CHART_VERSION:=$(shell grep version: etc/kubernetes/helm/enterprise-gateway/Chart.yaml | sed 's/version: //')
HELM_CHART_PACKAGE:=dist/enterprise-gateway-$(HELM_CHART_VERSION).tgz
HELM_CHART:=dist/jupyter_enterprise_gateway_helm-$(VERSION).tar.gz
HELM_CHART_DIR:=etc/kubernetes/helm/enterprise-gateway
HELM_CHART_FILES:=$(shell find $(HELM_CHART_DIR) -type f ! -name .DS_Store)
HELM_INSTALL_DIR?=/usr/local/bin

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

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
	-make -C docs clean
	-make -C etc clean

clean-env: ## Remove conda env
	-conda env remove -n $(ENV) -y

lint: ## Check code style
	@pip install -q -e ".[lint]"
	@pip install -q pipx
	ruff .
	black --check --diff --color .
	mdformat --check *.md
	pipx run 'validate-pyproject[all]' pyproject.toml
	pipx run interrogate -v .

run-dev: test-install-wheel ## Make a server in jupyter_websocket mode
	python enterprise_gateway

docs: ## Make HTML documentation
	make -C docs requirements html SPHINXOPTS="-W"

kernelspecs:  kernelspecs_all kernelspecs_yarn kernelspecs_conductor kernelspecs_kubernetes kernelspecs_docker kernel_image_files ## Create archives with sample kernelspecs
kernelspecs_all kernelspecs_yarn kernelspecs_conductor kernelspecs_kubernetes kernelspecs_docker kernel_image_files:
	make VERSION=$(VERSION) TAG=$(TAG) SPARK_VERSION=$(SPARK_VERSION) -C  etc $@

test-install: dist test-install-wheel test-install-tar ## Install and minimally run EG with the wheel and tar distributions

test-install-wheel:
	pip uninstall -y jupyter_enterprise_gateway
	pip install dist/jupyter_enterprise_gateway-*.whl && \
		jupyter enterprisegateway --help

test-install-tar:
	pip uninstall -y jupyter_enterprise_gateway
	pip install dist/jupyter_enterprise_gateway-*.tar.gz && \
		jupyter enterprisegateway --help

bdist: $(WHEEL_FILE)

$(WHEEL_FILE): $(WHEEL_FILES)
	pip install build && python -m build --wheel . \
		&& rm -rf *.egg-info && chmod 0755 dist/*.*

sdist: $(SDIST_FILE)

$(SDIST_FILE): $(WHEEL_FILES)
	pip install build && python -m build --sdist . \
		&& rm -rf *.egg-info && chmod 0755 dist/*.*

helm-chart: helm-install $(HELM_CHART) ## Make helm chart distribution

helm-install: $(HELM_INSTALL_DIR)/helm

$(HELM_INSTALL_DIR)/helm: # Download and install helm
	curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 -o /tmp/get_helm.sh \
	&& chmod +x /tmp/get_helm.sh \
	&& DESIRED_VERSION=$(HELM_DESIRED_VERSION) /tmp/get_helm.sh \
	&& rm -f /tmp/get_helm.sh

helm-lint: helm-clean
	helm lint $(HELM_CHART_DIR)

helm-clean: # Remove any .DS_Store files that might wind up in the package
	$(shell find etc/kubernetes/helm -type f -name '.DS_Store' -exec rm -f {} \;)

$(HELM_CHART): $(HELM_CHART_FILES)
	make helm-lint
	helm package $(HELM_CHART_DIR) -d dist
	mv $(HELM_CHART_PACKAGE) $(HELM_CHART)  # Rename output to match other assets

dist: lint bdist sdist kernelspecs helm-chart ## Make source, binary, kernelspecs and helm chart distributions to dist folder

TEST_DEBUG_OPTS:=

test-debug:
	make TEST_DEBUG_OPTS="--nocapture --nologcapture --logging-level=10" test

test: TEST?=
test: ## Run unit tests
ifeq ($(TEST),)
	pytest -vv $(TEST_DEBUG_OPTS)
else
# e.g., make test TEST="test_gatewayapp.py::TestGatewayAppConfig"
	pytest -vv $(TEST_DEBUG_OPTS) enterprise_gateway/tests/$(TEST)
endif

release: dist check_dists ## Make a wheel + source release on PyPI
	twine upload $(DIST_FILES)

check_dists:
	pip install twine && twine check --strict $(DIST_FILES)

# Here for doc purposes
docker-images:  ## Build docker images (includes kernel-based images)
kernel-images: ## Build kernel-based docker images

# Actual working targets...
docker-images: demo-base enterprise-gateway-demo kernel-images enterprise-gateway kernel-py kernel-spark-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py kernel-image-puller

enterprise-gateway-demo kernel-images enterprise-gateway kernel-py kernel-spark-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py kernel-image-puller:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) NO_CACHE=$(NO_CACHE) TAG=$(TAG) SPARK_VERSION=$(SPARK_VERSION) MULTIARCH_BUILD=$(MULTIARCH_BUILD) TARGET_ARCH=$(TARGET_ARCH) -C etc $@

demo-base:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) NO_CACHE=$(NO_CACHE) TAG=$(SPARK_VERSION) SPARK_VERSION=$(SPARK_VERSION) MULTIARCH_BUILD=$(MULTIARCH_BUILD) TARGET_ARCH=$(TARGET_ARCH) -C etc $@

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
	(GATEWAY_HOST=$(ITEST_YARN_HOST) LOG_LEVEL=$(LOG_LEVEL) KERNEL_USERNAME=$(ITEST_USER) KERNEL_LAUNCH_TIMEOUT=$(ITEST_KERNEL_LAUNCH_TIMEOUT) SPARK_VERSION=$(SPARK_VERSION) ITEST_HOSTNAME_PREFIX=$(ITEST_HOSTNAME_PREFIX) pytest -vv $(TEST_DEBUG_OPTS) $(ITEST_YARN_TESTS))
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
	(GATEWAY_HOST=$(ITEST_DOCKER_HOST) LOG_LEVEL=$(LOG_LEVEL) KERNEL_USERNAME=$(ITEST_USER) KERNEL_LAUNCH_TIMEOUT=$(ITEST_KERNEL_LAUNCH_TIMEOUT) $(ITEST_DOCKER_KERNELS) ITEST_HOSTNAME_PREFIX=$(ITEST_USER) pytest -vv $(TEST_DEBUG_OPTS) $(ITEST_DOCKER_TESTS))
	@echo "Run \`docker service logs itest-docker\` to see enterprise-gateway log."

PREP_TIMEOUT?=180
itest-docker-prep:
	@-docker service rm enterprise-gateway_enterprise-gateway enterprise-gateway_enterprise-gateway-proxy
	@-docker swarm leave --force
	# Check if swarm mode is active, if not attempt to create the swarm
	@(docker info | grep -q 'Swarm: active'; if [ $$? -eq 1 ]; then docker swarm init; fi;)
	@echo "Starting enterprise-gateway swarm service (run \`docker service logs enterprise-gateway_enterprise-gateway\` to see service log)..."
	@KG_PORT=${ITEST_DOCKER_PORT} EG_DOCKER_NETWORK=enterprise-gateway docker stack deploy -c etc/docker/docker-compose.yml enterprise-gateway
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt $(PREP_TIMEOUT) ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker service logs enterprise-gateway_enterprise-gateway 2>&1 |grep --regexp "Jupyter Enterprise Gateway .* is available at http"; r=$$?; done; if [ $$attempts -ge $(PREP_TIMEOUT) ]; then echo "Wait for startup timed out!"; exit 1; fi;)
