# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from tornado import web
import notebook.base.handlers as notebook_handlers
from ..mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin

class APIVersionHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        notebook_handlers.APIVersionHandler):
    pass

class NotFoundHandler(JSONErrorsMixin, web.RequestHandler):
    '''Catches all requests and respondes with 404 JSON messages.'''
    def prepare(self):
        raise web.HTTPError(404)

default_handlers = [
    (r'/api', APIVersionHandler),
    (r'/(.*)', NotFoundHandler)
]
