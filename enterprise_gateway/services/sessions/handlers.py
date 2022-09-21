# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for session CRUD."""
from typing import List

import jupyter_server.services.sessions.handlers as jupyter_server_handlers
import tornado
from jupyter_server.utils import ensure_async

from ...mixins import CORSMixin, JSONErrorsMixin, TokenAuthorizationMixin


class SessionRootHandler(
    TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, jupyter_server_handlers.SessionRootHandler
):
    """Extends the jupyter_server root session handler with token auth, CORS, and
    JSON errors.
    """

    async def get(self) -> None:
        """Overrides the super class method to honor the kernel listing
        configuration setting.

        Raises
        ------
        tornado.web.HTTPError
            If eg_list_kernels is False, respond with 403 Forbidden
        """
        if "eg_list_kernels" not in self.settings or not self.settings["eg_list_kernels"]:
            raise tornado.web.HTTPError(403, "Forbidden")
        else:
            await ensure_async(super().get())


default_handlers: List[tuple] = []
for path, cls in jupyter_server_handlers.default_handlers:
    if cls.__name__ in globals():
        # Use the same named class from here if it exists
        default_handlers.append((path, globals()[cls.__name__]))
    else:
        # Everything should have CORS and token auth
        bases = (TokenAuthorizationMixin, CORSMixin, cls)
        default_handlers.append((path, type(cls.__name__, bases, {})))
