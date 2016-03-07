# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handler for kernel activity tracking."""

import tornado.web
import json
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin

class ActivityHandler(TokenAuthorizationMixin,
                      CORSMixin,
                      JSONErrorsMixin,
                      tornado.web.RequestHandler):

    @property
    def activity(self):
        return self.settings['activity_manager']

    def get(self):
        """Responds with a JSON object of stats about every running kernel if
        kernel listing, `kg_list_kernels`, is enabled on the server.

        Raises
        ------
        tornado.web.HTTPError
            If kg_list_kernels is False, respond with 403 Forbidden

        See Also
        --------
        manager.ActivityManager : Tracks kernel activity

        Examples
        --------

        {
          "0f41b09c-c5b4-4f28-a7db-2f779151c20f": {
            "last_message_to_client": "2014-09-08T19:40:17.819Z",
            "last_message_to_kernel": "2014-09-08T19:40:17.819Z",
            "last_time_state_changed": "2014-09-08T19:40:17.819Z",
            "busy" : false,
            "connections" : 0,
            "last_client_connect": "2014-09-08T19:40:17.819Z",
            "last_client_disconnect": "2014-09-08T19:40:17.819Z"
          }
        }
        """
        if not self.settings.get('kg_list_kernels'):
            raise tornado.web.HTTPError(403, 'Forbidden')
        self.set_header('Content-Type', 'application/json')
        self.set_status(200)
        self.finish(json.dumps(self.activity.get()))
