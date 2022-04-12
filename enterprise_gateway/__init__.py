# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
from ._version import __version__  # noqa

"""Lazy-loading entrypoint for the enterprise gateway package."""


def launch_instance(*args, **kwargs):
    from enterprise_gateway.enterprisegatewayapp import launch_instance

    launch_instance(*args, **kwargs)
