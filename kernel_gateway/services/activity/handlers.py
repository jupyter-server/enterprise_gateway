# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import tornado.web
import json
from .manager import activity
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin

class ActivityHandler(TokenAuthorizationMixin,
                      CORSMixin,
                      JSONErrorsMixin,
                      tornado.web.RequestHandler):

    def get(self, **kwargs):
        if not self.settings.get('kg_list_kernels'):
            raise tornado.web.HTTPError(403, 'Forbidden')
        self.set_header('Content-Type', 'application/json')
        self.set_status(200)
        self.finish(json.dumps(activity.get()))
