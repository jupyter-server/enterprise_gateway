# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for the base of the API."""

import json
from tornado import web
import notebook.base.handlers as notebook_handlers
import notebook._version
from ..mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from .._version import __version__


class APIVersionHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        notebook_handlers.APIVersionHandler):
    """Extends the notebook server base API handler with token auth, CORS, and
    JSON errors.
    """
    #pass

    def get(self):
        # not authenticated, so give as few info as possible
        self.finish(json.dumps({"version":notebook.__version__, "gateway_version":__version__}))


class NotFoundHandler(JSONErrorsMixin, web.RequestHandler):
    """Catches all requests and responds with 404 JSON messages.

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
