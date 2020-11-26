# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel specs."""
import os

from notebook.utils import maybe_future
from tornado import gen, web
from ...mixins import CORSMixin


class BaseSpecHandler(CORSMixin, web.StaticFileHandler):
    """Exposes the ability to return specifications from static files"""

    @staticmethod
    def get_resource_metadata():
        """Returns the (resource, mime-type) for the handlers spec.
        """
        pass

    def initialize(self):
        """Initializes the instance of this class to serve files.

        The handler is initialized to serve files from the directory
        where this module is defined.  `path` parameter will be overridden.
        """
        web.StaticFileHandler.initialize(self, path=os.path.dirname(__file__))

    @gen.coroutine
    def get(self):
        """Handler for a get on a specific handler
        """
        resource_name, content_type = self.get_resource_metadata()
        self.set_header('Content-Type', content_type)
        res = web.StaticFileHandler.get(self, resource_name)
        yield maybe_future(res)

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()


class SpecJsonHandler(BaseSpecHandler):
    """Exposes a JSON swagger specification"""
    @staticmethod
    def get_resource_metadata():
        return 'swagger.json', 'application/json'


class APIYamlHandler(BaseSpecHandler):
    """Exposes a YAML swagger specification"""
    @staticmethod
    def get_resource_metadata():
        return 'swagger.yaml', 'text/x-yaml'


default_handlers = [
    ('/api/{}'.format(SpecJsonHandler.get_resource_metadata()[0]), SpecJsonHandler),
    ('/api/{}'.format(APIYamlHandler.get_resource_metadata()[0]), APIYamlHandler)
]
