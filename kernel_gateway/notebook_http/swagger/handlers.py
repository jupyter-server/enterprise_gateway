# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handler that returns the swagger specification of a
notebook-http mode, notebook-defined API.
"""

import tornado.web
import json
from .builders import SwaggerSpecBuilder
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin

class SwaggerSpecHandler(TokenAuthorizationMixin,
                         CORSMixin,
                         JSONErrorsMixin,
                         tornado.web.RequestHandler):
    """Handles requests for the Swagger specification of a notebook defined
    API.
    """
    output = None

    def initialize(self, notebook_path, source_cells, kernel_spec):
        """Builds the spec for the notebook-defined API.

        Parameters
        ----------
        notebook_path : str
            Path to the notebook, used to set the API title
        source_cells : list
            Source code cell strings
        kernel_spec : str
            Name of the notebook kernel language
        """
        if self.output is None:
            spec_builder = SwaggerSpecBuilder(kernel_spec)
            for source_cell in source_cells:
                spec_builder.add_cell(source_cell)
            spec_builder.set_title(notebook_path)
            SwaggerSpecHandler.output = json.dumps(spec_builder.build())

    def get(self, **kwargs):
        """Responds with the spec in JSON format."""
        self.set_header('Content-Type', 'application/json')
        self.set_status(200)
        self.finish(self.output)
