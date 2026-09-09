"""Tornado handlers for the base of the API."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.


import json
from typing import List

import jupyter_server._version
import prometheus_client
from jupyter_server.base.handlers import APIHandler
from tornado import web

from .._version import __version__
from ..mixins import CORSMixin, JSONErrorsMixin, TokenAuthorizationMixin


class APIVersionHandler(TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, APIHandler):
    """ "
    Extends the jupyter_server base API handler with token auth, CORS, and
    JSON errors to produce version information for jupyter_server and gateway.
    """

    def get(self):
        """Get the API version."""
        # not authenticated, so give as few info as possible
        # to be backwards compatibile, use only 'version' for the jupyter_server version
        # and be more specific for gateway_version
        self.finish(
            json.dumps({"version": jupyter_server.__version__, "gateway_version": __version__})
        )


class PrometheusMetricsHandler(CORSMixin, web.RequestHandler):
    """
    Return prometheus metrics from this enterprise gateway
    """

    def get(self):
        """Get the latest state of the Prometheus' metrics."""
        self.set_header("Content-Type", prometheus_client.CONTENT_TYPE_LATEST)
        self.write(prometheus_client.generate_latest(prometheus_client.REGISTRY))


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
        """Prepare the response."""
        raise web.HTTPError(404)


default_handlers: List[tuple] = [
    (r"/api", APIVersionHandler),
    (r"/metrics", PrometheusMetricsHandler),
    (r"/(.*)", NotFoundHandler),
]
