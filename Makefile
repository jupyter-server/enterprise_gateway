# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

.PHONY: bash bdist_wheel dev help sdist test

REPO:=jupyter/minimal-notebook:latest
define DOCKER
docker run -it --rm \
	-p 9502:8888 \
	--workdir /srv/kernel_gateway \
	-v `pwd`:/srv/kernel_gateway \
	$(REPO)
endef

help:
	@cat Makefile

bash:
	@$(DOCKER) bash

dev:
	@$(DOCKER) python kernel_gateway

test:
	@$(DOCKER) python3 -B -m unittest discover

sdist:
	@$(DOCKER) python setup.py sdist

bdist_wheel:
	@$(DOCKER) python setup.py bdist_wheel
