# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: help build clean nuke dev dev-http docs kernelspecs install bdist sdist test release

SA:=source activate
ENV:=enterprise-gateway-dev
SHELL:=/bin/bash
MAKEFILE_DIR:=${CURDIR}

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

kernelspecs: ## Make a tar.gz file consisting of kernelspec files
	@mkdir -p build/kernelspecs
	cp -r etc/kernelspecs build
	@echo build/kernelspecs/*_python_* | xargs -t -n 1 cp -r etc/kernel-launchers/python/*
	@echo build/kernelspecs/*_R_* | xargs -t -n 1 cp -r etc/kernel-launchers/R/*
	@echo build/kernelspecs/*_scala_* | xargs -t -n 1 cp -r etc/kernel-launchers/scala/*
	@mkdir -p dist
	rm -f dist/enterprise_gateway-kernelspecs.tar.gz
	@( cd build/kernelspecs; tar -pvczf "$(MAKEFILE_DIR)/dist/enterprise_gateway_kernelspecs.tar.gz" * )

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
	$(SA) $(ENV) && python setup.py bdist_wheel $(POST_SDIST) -r pypi && rm -rf *.egg-info

sdist: ## Make a dist/*.tar.gz source distribution
	$(SA) $(ENV) && python setup.py sdist $(POST_SDIST) -r pypi && rm -rf *.egg-info

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
