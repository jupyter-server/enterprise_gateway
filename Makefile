# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: bash bdist_wheel dev help sdist test

REPO:=jupyter/minimal-notebook:latest
define DOCKER
docker run -it --rm \
	-p 9502:8888 \
	-e PYTHONPATH=/srv/kernel_gateway \
	--workdir /srv/kernel_gateway \
	-v `pwd`:/srv/kernel_gateway \
	$(REPO)
endef

help:
	@cat Makefile

bash:
	@$(DOCKER) bash

dev:
	@$(DOCKER) python kernel_gateway --KernelGatewayApp.ip='0.0.0.0'

# usage:
# make test
# make test TEST="kernel_gateway.tests.test_gatewayapp.TestGatewayAppConfig"
test: TEST?=
test:
ifeq ($(TEST),)
	@$(DOCKER) python3 -B -m unittest discover
else
	@$(DOCKER) python3 -B -m unittest $(TEST)
endif

sdist:
	@$(DOCKER) python setup.py sdist

bdist_wheel:
	@$(DOCKER) python setup.py bdist_wheel
