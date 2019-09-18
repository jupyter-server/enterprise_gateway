# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel specs."""

import notebook.services.kernelspecs.handlers as notebook_handlers
import notebook.kernelspecs.handlers as notebook_kernelspecs_resources_handlers

from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin

# Extends the default handlers from the notebook package with token auth, CORS
# and JSON errors.
default_handlers = []
for path, cls in notebook_handlers.default_handlers:
    # Everything should have CORS and token auth
    bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
    default_handlers.append((path, type(cls.__name__, bases, {})))

for path, cls in notebook_kernelspecs_resources_handlers.default_handlers:
    # Everything should have CORS and token auth
    bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
    default_handlers.append((path, type(cls.__name__, bases, {})))
