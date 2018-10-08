# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs install sdist test release clean-docker clean-docker-enterprise-gateway \
    clean-docker-nb2kg clean-docker-yarn-spark clean-kubernetes clean-enterprise-gateway \
    clean-kernel-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py \
    clean-kernel-tf-gpu-py kubernetes-publish

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
kubernetes-images: ## Build kubernetes docker images
enterprise-gateway: ## Build elyra/enterprise-gateway:dev docker image
kernel-py: ## Build elyra/kernel-py:dev docker image
kernel-r: ## Build elyra/kernel-r:dev docker image
kernel-spark-r: ## Build elyra/kernel-spark-r:dev docker image
kernel-scala: ## Build elyra/kernel-scala:dev docker image
kernel-tf-py: ## Build elyra/kernel-tf-py:dev docker image
kernel-tf-gpu-py: ## Build elyra/kernel-tf-gpu-py:dev docker image

# Actual working targets...
docker-images enterprise-gateway-demo yarn-spark nb2kg kubernetes-images enterprise-gateway kernel-py kernel-r kernel-spark-r kernel-scala kernel-tf-py kernel-tf-gpu-py:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

docker-image-enterprise-gateway: $(WHEEL_FILE)
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@


# Here for doc purposes
clean-docker: ## Remove docker images
clean-enterprise-gateway-demo: ## Remove elyra/enterprise-gateway-demo:dev docker image
clean-nb2kg: ## Remove elyra/nb2kg:dev docker image
clean-yarn-spark: ## Remove elyra/yarn-spark:2.3.1 docker image
clean-kubernetes: ## Remove kubernetes docker images
clean-enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
clean-kernel-py: ## Remove elyra/kernel-py:dev docker image
clean-kernel-r: ## Remove elyra/kernel-r:dev docker image
clean-kernel-spark-r: ## Remove elyra/kernel-spark-r:dev docker image
clean-kernel-scala: ## Remove elyra/kernel-scala:dev docker image
clean-kernel-tf-py: ## Remove elyra/kernel-tf-py:dev docker image
clean-kernel-tf-gpu-py: ## Remove elyra/kernel-tf-gpu-py:dev docker image

clean-docker clean-enterprise-gateway-demo clean-nb2kg clean-yarn-spark clean-kubernetes clean-enterprise-gateway clean-kernel-py clean-kernel-r clean-kernel-spark-r clean-kernel-scala clean-kernel-tf-py clean-kernel-tf-gpu-py:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

kubernetes-publish: ## Push kubernetes docker images to docker hub
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

# itest should have these targets up to date: bdist kernelspecs docker-enterprise-gateway 

# itest configurable settings
# indicates which host (gateway) to connect to...
ITEST_HOST?=localhost:8888
# indicates two things:
# this prefix is used by itest to determine hostname to test against, in addtion,
# if itests will be run locally with docker-prep target, this will set the hostname within that container as well
export ITEST_HOSTNAME_PREFIX?=itest
# indicates the user to emulate.  This equates to 'KERNEL_USERNAME'...
ITEST_USER?=bob
# indicates the other set of options to use.  At this time, only the python notebooks succeed, so we're skipping R and Scala.
ITEST_OPTIONS?=

ENTERPRISE_GATEWAY_TAG?=dev

# here's an example of the options (besides host and user) with their expected values ...
# ITEST_OPTIONS=--impersonation < True | False >

PREP_DOCKER?=1
itest: ## Run integration tests (optionally) against docker container
ifeq (1, $(PREP_DOCKER))
	make docker-prep
endif
	($(SA) $(ENV) && GATEWAY_HOST=$(ITEST_HOST) KERNEL_USERNAME=$(ITEST_USER) nosetests -v enterprise_gateway.itests)
	@echo "Run \`docker logs $(ITEST_HOSTNAME_PREFIX)\` to see enterprise-gateway log."

PREP_TIMEOUT?=60
docker-prep: 
	@-docker rm -f $(ITEST_HOSTNAME_PREFIX) >> /dev/null
	@echo "Starting enterprise-gateway container (run \`docker logs itest\` to see container log)..."
	@-docker run -itd -p 8888:8888 -h itest --name itest -e ITEST_HOSTNAME_PREFIX -v `pwd`/enterprise_gateway/itests:/tmp/byok elyra/enterprise-gateway-demo:$(ENTERPRISE_GATEWAY_TAG) --elyra
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt $(PREP_TIMEOUT) ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker logs $(ITEST_HOSTNAME_PREFIX) |grep 'Jupyter Enterprise Gateway at http'; r=$$?; done; if [ $$attempts -ge $(PREP_TIMEOUT) ]; then echo "Wait for startup timed out!"; exit 1; fi;)
