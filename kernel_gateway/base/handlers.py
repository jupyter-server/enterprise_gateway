# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import notebook.base.handlers as notebook_handlers
from ..mixins import TokenAuthorizationMixin, CORSMixin

class APIVersionHandler(TokenAuthorizationMixin, 
                        CORSMixin, 
                        notebook_handlers.APIVersionHandler):
    pass

default_handlers = [
    (r"/api", APIVersionHandler)
]
