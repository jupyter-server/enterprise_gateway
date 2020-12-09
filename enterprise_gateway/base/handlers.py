# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for the base of the API."""

import json
import notebook._version
from notebook.base.handlers import APIHandler
from tornado import web
from ..mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from .._version import __version__


class APIVersionHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        APIHandler):
    """"
    Extends the notebook server base API handler with token auth, CORS, and
    JSON errors to produce version information for notebook and gateway.
    """
    def get(self):
        # not authenticated, so give as few info as possible
        # to be backwards compatibile, use only 'version' for the notebook version
        # and be more specific for gateway_version
        self.finish(json.dumps({"version": notebook.__version__, "gateway_version": __version__}))


class NotFoundHandler(JSONErrorsMixin, web.RequestHandler):
    """
    Catches all requests and responds with 404 JSON messages.

    Installed as the fallback error for all unhandled requests.

    Raises
    ------
    tornado.web.HTTPError
        Always 404 Not Found
    """
    def prepare(self):
        raise web.HTTPError(404)


default_handlers = [
    (r'/api', APIVersionHandler),
    (r'/(.*)', NotFoundHandler)
]
