# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs kernelspecs install sdist test release docker-clean docker-clean-enterprise-gateway docker-clean-nb2kg docker-clean-yarn-spark

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash

VERSION:=0.9.0.dev0

WHEEL_FILE:=dist/jupyter_enterprise_gateway-$(VERSION)-py2.py3-none-any.whl
WHEEL_FILES:=$(shell find . -type f ! -path "./build/*" ! -path "./etc/*" ! -path "./docs/*" ! -path "./.git/*" ! -path "./.idea/*" ! -path "./dist/*" ! -path "./.image-enterprise-gateway" ! -path "./.image-nb2kg" ! -path "./.image-yarn-spark" )

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

dist: bdist sdist ## Make binary and source distribution to dist folder

test: TEST?=
test: ## Run unit tests
ifeq ($(TEST),)
	$(SA) $(ENV) && nosetests -v
else
# e.g., make test TEST="test_gatewayapp.TestGatewayAppConfig"
	$(SA) $(ENV) && nosetests -v enterprise_gateway.tests.$(TEST)
endif

release: POST_SDIST=upload
release: bdist sdist ## Make a wheel + source release on PyPI

# Here for doc purposes
docker-images:  ## Build docker images
docker-image-enterprise-gateway:  ## Build elyra/enterprise-gateway:dev docker image
docker-image-yarn-spark:  ## Build elyra/yarn-spark:2.1.0 docker image
docker-image-nb2kg:  ## Build elyra/nb2kg:dev docker image 

# Actual working targets...
docker-images docker-image-yarn-spark docker-image-nb2kg:  
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@

docker-image-enterprise-gateway: $(WHEEL_FILE) 
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@


# Here for doc purposes
docker-clean: ## Remove docker images
docker-clean-enterprise-gateway: ## Remove elyra/enterprise-gateway:dev docker image
docker-clean-nb2kg: ## Remove elyra/nb2kg:dev docker image
docker-clean-yarn-spark: ## Remove elyra/yarn-spark:2.1.0 docker image

docker-clean docker-clean-enterprise-gateway docker-clean-nb2kg docker-clean-yarn-spark:
	make WHEEL_FILE=$(WHEEL_FILE) VERSION=$(VERSION) -C etc $@


# itest should have these targets up to date: bdist kernelspecs docker-image-enterprise-gateway 

# itest configurable settings
# indicates which host (gateway) to connect to...
ITEST_HOST:=localhost:8888
# indicates the user to emulate.  This equates to 'KERNEL_USERNAME'...
ITEST_USER:=bob
# indicates the other set of options to use.  At this time, only the python notebooks succeed, so we're skipping R and Scala.
ITEST_OPTIONS:=

ENTERPRISE_GATEWAY_TAG:=dev

# here's an example of the options (besides host and user) with their expected values ...
# ITEST_OPTIONS=--impersonation < True | False >

PREP_DOCKER:=1
itest: ## Run integration tests (optionally) against docker container
ifeq (1, $(PREP_DOCKER))
	make docker-prep
endif
	(cd enterprise_gateway/itests/src/; pytest *_testcase.py --host=$(ITEST_HOST) --username=$(ITEST_USER) $(ITEST_OPTIONS))
	@echo "Run \`docker logs itest\` to see enterprise-gateway log."

docker-prep: 
	@-docker rm -f itest >> /dev/null
	@echo "Starting enterprise-gateway container (run \`docker logs itest\` to see container log)..."
	@-docker run -itd -p 8888:8888 -h itest --name itest elyra/enterprise-gateway:$(ENTERPRISE_GATEWAY_TAG) --elyra
	@(r="1"; attempts=0; while [ "$$r" == "1" -a $$attempts -lt 30 ]; do echo "Waiting for enterprise-gateway to start..."; sleep 2; ((attempts++)); docker logs itest |grep 'Jupyter Enterprise Gateway at http'; r=$$?; done; if [ $$attempts -ge 30 ]; then echo "Wait for startup timed out!"; exit 1; fi;)
