# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import notebook.services.kernelspecs.handlers as notebook_handlers
from ...mixins import TokenAuthorizationMixin, CORSMixin

default_handlers = []
for path, cls in notebook_handlers.default_handlers:
    # Everything should have CORS and token auth
    bases = (TokenAuthorizationMixin, CORSMixin, cls)
    default_handlers.append((path, type(cls.__name__, bases, {})))
