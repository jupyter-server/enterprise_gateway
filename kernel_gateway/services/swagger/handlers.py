# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import tornado.web
import json
from .builders import *
from ...mixins import TokenAuthorizationMixin, CORSMixin

class SwaggerSpecHandler(TokenAuthorizationMixin, CORSMixin, tornado.web.RequestHandler):
    '''A tornado handler to serve requests for a swagger specification.
    Given a collection of cell sources, notebook title and kernel name, this
    handler will generate a swagger specification describing the API.
    '''
    output = '{}'

    def initialize(self, title, source_cells, kernel_spec):
        spec_builder = SwaggerSpecBuilder(kernel_spec)
        for source_cell in source_cells:
            spec_builder.add_cell(source_cell)
        spec_builder.set_title(title)
        self.output = json.dumps(spec_builder.build())

    def get(self, **kwargs):
        self.set_header('Content-Type', 'application/json')
        self.set_status(200)
        self.finish(self.output)
