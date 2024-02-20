"""Tornado handlers for kernel specs."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os
from typing import List

from jupyter_server.utils import ensure_async
from tornado import web

from ...mixins import CORSMixin


class BaseSpecHandler(CORSMixin, web.StaticFileHandler):
    """Exposes the ability to return specifications from static files"""

    @staticmethod
    def get_resource_metadata() -> tuple:
        """Returns the (resource, mime-type) for the handlers spec."""
        pass

    def initialize(self) -> None:
        """Initializes the instance of this class to serve files.

        The handler is initialized to serve files from the directory
        where this module is defined.  `path` parameter will be overridden.
        """
        web.StaticFileHandler.initialize(self, path=os.path.dirname(__file__))

    async def get(self) -> None:
        """Handler for a get on a specific handler"""
        resource_name, content_type = self.get_resource_metadata()
        self.set_header("Content-Type", content_type)
        res = web.StaticFileHandler.get(self, resource_name)
        await ensure_async(res)

    def options(self, **kwargs) -> None:
        """Method for properly handling CORS pre-flight"""
        self.finish()


class SpecJsonHandler(BaseSpecHandler):
    """Exposes a JSON swagger specification"""

    @staticmethod
    def get_resource_metadata() -> tuple:
        """Get the resource metadata."""
        return "swagger.json", "application/json"


class APIYamlHandler(BaseSpecHandler):
    """Exposes a YAML swagger specification"""

    @staticmethod
    def get_resource_metadata() -> tuple:
        """Get the resource metadata."""
        return "swagger.yaml", "text/x-yaml"


default_handlers: List[tuple] = [
    (f"/api/{SpecJsonHandler.get_resource_metadata()[0]}", SpecJsonHandler),
    (f"/api/{APIYamlHandler.get_resource_metadata()[0]}", APIYamlHandler),
]
