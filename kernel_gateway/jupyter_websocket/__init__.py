# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Jupyter websocket personality for the Kernel Gateway"""

import os
from ..base.handlers import default_handlers as default_base_handlers
from ..services.kernels.pool import KernelPool
from ..services.kernels.handlers import default_handlers as default_kernel_handlers
from ..services.kernelspecs.handlers import default_handlers as default_kernelspec_handlers
from ..services.sessions.handlers import default_handlers as default_session_handlers
from .handlers import default_handlers as default_api_handlers
from notebook.utils import url_path_join
from traitlets import Bool, List, default
from traitlets.config.configurable import LoggingConfigurable


class JupyterWebsocketPersonality(LoggingConfigurable):
    """Personality for standard websocket functionality, registering
    endpoints that are part of the Jupyter Kernel Gateway API
    """

    list_kernels_env = 'KG_LIST_KERNELS'
    list_kernels = Bool(config=True,
        help="""Permits listing of the running kernels using API endpoints /api/kernels
            and /api/sessions (KG_LIST_KERNELS env var). Note: Jupyter Notebook
            allows this by default but kernel gateway does not."""
    )

    @default('list_kernels')
    def list_kernels_default(self):
        return os.getenv(self.list_kernels_env, 'False') == 'True'

    env_whitelist_env = 'KG_ENV_WHITELIST'
    env_whitelist = List(config=True,
                             help="""Environment variables allowed to be set when
                             a client requests a new kernel""")

    @default('env_whitelist')
    def env_whitelist_default(self):
        return os.getenv(self.env_whitelist_env, '').split(',')

    def init_configurables(self):
        self.kernel_pool = KernelPool(
            self.parent.prespawn_count,
            self.parent.kernel_manager
        )

    def create_request_handlers(self):
        """Create default Jupyter handlers and redefine them off of the
        base_url path. Assumes init_configurables() has already been called.
        """
        handlers = []

        # append tuples for the standard kernel gateway endpoints
        for handler in (
            default_api_handlers +
            default_kernel_handlers +
            default_kernelspec_handlers +
            default_session_handlers +
            default_base_handlers
        ):
            # Create a new handler pattern rooted at the base_url
            pattern = url_path_join('/', self.parent.base_url, handler[0])
            # Some handlers take args, so retain those in addition to the
            # handler class ref
            new_handler = tuple([pattern] + list(handler[1:]))
            handlers.append(new_handler)
        return handlers

    def should_seed_cell(self, code):
        """Determines whether the given code cell source should be executed when
        seeding a new kernel."""
        # seed all code cells
        return True

    def shutdown(self):
        """Stop all kernels in the pool."""
        self.kernel_pool.shutdown()


def create_personality(*args, **kwargs):
    return JupyterWebsocketPersonality(*args, **kwargs)
