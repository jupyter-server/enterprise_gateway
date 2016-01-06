# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import tornado.web
from tornado.log import access_log
from tornado import gen
import json
from .builders import *
from random import random

class SwaggerSpecHandler(tornado.web.RequestHandler):
    output = '{}'

    def initialize(self, title ,endpoints, kernel_spec):
        spec_builder = SwaggerSpecBuilder(kernel_spec)
        for _, verb_source_map in endpoints:
            for source in list(verb_source_map.values()):
                spec_builder.add_cell(source)
        spec_builder.set_title(title)
        self.output = json.dumps(spec_builder.build())

    def get(self, **kwargs):
        self.set_header('Content-Type', 'application/json')
        self.set_status(200)
        self.finish(self.output)
