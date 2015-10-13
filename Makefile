# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: bash clean dev help sdist test

REPO:=jupyter/minimal-notebook:4.0
define DOCKER
docker run -it --rm \
	-p 8888:8888 \
	-e PYTHONPATH=/srv/kernel_gateway \
	--workdir /srv/kernel_gateway \
	-v `pwd`:/srv/kernel_gateway \
	$(REPO)
endef

help:
	@cat Makefile

bash:
	@$(DOCKER) bash

clean:
	@-rm -rf dist
	@-rm -rf *.egg-info
	@-find . -name __pycache__ -exec rm -fr {} \;

dev: ARGS?=
dev:
	$(DOCKER) python kernel_gateway --KernelGatewayApp.ip='0.0.0.0' $(ARGS)

sdist:
	@$(DOCKER) python setup.py sdist && rm -rf *.egg-info

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
