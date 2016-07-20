# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: bash clean dev help install sdist test docs

IMAGE:=jupyter/kernel-gateway-dev

DOCKER_ARGS?=
define DOCKER
docker run -it --rm \
	--workdir '/srv/kernel_gateway' \
	-e PYTHONPATH='/srv/kernel_gateway' \
	-v `pwd`:/srv/kernel_gateway $(DOCKER_ARGS)
endef

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

bash: ## Start a bash shell within the dev container
	@$(DOCKER) -p 8888:8888 $(IMAGE) bash

clean: ## Remove all built files from the host (but not the dev docker image)
	@-rm -rf dist
	@-rm -rf build
	@-rm -rf *.egg-info
	@-find kernel_gateway -name __pycache__ -exec rm -fr {} \;
	@-find kernel_gateway -name '*.pyc' -exec rm -fr {} \;
	@-make -C docs clean

dev: ARGS?=
dev: PYARGS?=
dev: ## Start kernel gateway on port 8888 in a docker container
	$(DOCKER) -p 8888:8888 $(IMAGE) \
		python $(PYARGS) kernel_gateway --KernelGatewayApp.ip='0.0.0.0' $(ARGS)

docs: ## Build the sphinx documentation in a container
	$(DOCKER) $(IMAGE) bash -c "source activate kernel_gateway_docs && make -C docs html"

etc/api_examples/%: ## Start one of the notebook-http mode API examples on port 8888 in a docker container
	$(DOCKER) -p 8888:8888 $(IMAGE) \
		python $(PYARGS) kernel_gateway --KernelGatewayApp.ip='0.0.0.0' \
			--KernelGatewayApp.api='kernel_gateway.notebook_http' \
			--KernelGatewayApp.seed_uri=/srv/kernel_gateway/$@.ipynb $(ARGS)

build: image

image: ## Build the dev/test docker image
	@docker build --rm -f Dockerfile.dev -t $(IMAGE) .

install: ## Test install of dist/*.whl and dist/*.tar.gz
	$(DOCKER) $(IMAGE) bash -c "pip install dist/*.whl && \
		jupyter kernelgateway --help && \
		pip uninstall -y jupyter_kernel_gateway "
	$(DOCKER) $(IMAGE) bash -c "pip install dist/*.tar.gz && \
		jupyter kernelgateway --help && \
		pip uninstall -y jupyter_kernel_gateway"

bdist: ## Build dist/*.whl binary distribution
	$(DOCKER) $(IMAGE) python setup.py bdist_wheel $(POST_SDIST) \
	&& rm -rf *.egg-info

sdist: ## Build a dist/*.tar.gz source distribution
	$(DOCKER) $(IMAGE) python setup.py sdist $(POST_SDIST) \
	&& rm -rf *.egg-info

test: test-python3 ## Run tests on Python 3 in a docker container

test-python2: PRE_CMD:=source activate python2;
test-python2: _test ## Run tests on Python 2 in a docker container

test-python3: _test

_test: TEST?=
_test:
ifeq ($(TEST),)
	$(DOCKER) $(IMAGE) bash -c "$(PRE_CMD) nosetests"
else
# e.g., make test TEST="test_gatewayapp.TestGatewayAppConfig"
	@$(DOCKER) $(IMAGE) bash -c  "$(PRE_CMD) nosetests kernel_gateway.tests.$(TEST)"
endif

release: POST_SDIST=register upload
release: bdist sdist ## Build wheel/source dists, register them on PyPI, and upload them all from a clean docker container
