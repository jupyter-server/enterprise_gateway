# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs install bdist sdist test release

SA:=source activate
ENV:=kernel-gateway-dev
SHELL:=/bin/bash

help:
# http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

build:
env: ## Make a dev environment
	conda create -y -n $(ENV) -c conda-forge --file requirements.txt \
		--file requirements-test.txt
	source activate $(ENV) && \
		pip install -r requirements-doc.txt && \
		pip install -e .

activate: ## eval `make activate`
	@echo "$(SA) $(ENV)"

clean: ## Make a clean source tree
	-rm -rf dist
	-rm -rf build
	-rm -rf *.egg-info
	-find kernel_gateway -name __pycache__ -exec rm -fr {} \;
	-find kernel_gateway -name '*.pyc' -exec rm -fr {} \;
	-$(SA) $(ENV) && make -C docs clean

nuke: ## Make clean + remove conda env
	-conda env remove -n $(ENV) -y

dev: ## Make a server in jupyter_websocket mode
	$(SA) $(ENV) && python kernel_gateway

dev-http: ## Make a server in notebook_http mode
	$(SA) $(ENV) && python kernel_gateway \
			--KernelGatewayApp.api='kernel_gateway.notebook_http' \
			--KernelGatewayApp.seed_uri=etc/api_examples/api_intro.ipynb

docs: ## Make HTML documentation
	$(SA) $(ENV) && make -C docs html

install: ## Make a conda env with dist/*.whl and dist/*.tar.gz installed
	-conda env remove -y -n $(ENV)-install
	conda create -y -n $(ENV)-install python=3 pip
	$(SA) $(ENV)-install && \
		pip install dist/*.whl && \
			jupyter kernelgateway --help && \
			pip uninstall -y jupyter_kernel_gateway
	conda env remove -y -n $(ENV)-install

	conda create -y -n $(ENV)-install python=3 pip
	$(SA) $(ENV)-install && \
		pip install dist/*.tar.gz && \
			jupyter kernelgateway --help && \
			pip uninstall -y jupyter_kernel_gateway
	conda env remove -y -n $(ENV)-install

bdist: ## Make a dist/*.whl binary distribution
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
	$(SA) $(ENV) && nosetests kernel_gateway.tests.$(TEST)
endif

release: POST_SDIST=register upload
release: bdist sdist ## Make a wheel + source release on PyPI
