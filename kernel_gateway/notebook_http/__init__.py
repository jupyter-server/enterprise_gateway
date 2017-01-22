# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Notebook HTTP personality for the Kernel Gateway"""

import os
import tornado
import importlib
from ..base.handlers import default_handlers as default_base_handlers
from ..services.kernels.pool import ManagedKernelPool
from .cell.parser import APICellParser
from .swagger.handlers import SwaggerSpecHandler
from .handlers import NotebookAPIHandler, parameterize_path, NotebookDownloadHandler
from notebook.utils import url_path_join
from traitlets import Bool, Unicode, Dict, default
from traitlets.config.configurable import LoggingConfigurable


class NotebookHTTPPersonality(LoggingConfigurable):
    """Personality for notebook-http support, creating REST endpoints
    based on the notebook's annotated cells
    """
    cell_parser_env = 'KG_CELL_PARSER'
    cell_parser = Unicode('kernel_gateway.notebook_http.cell.parser',
        config=True,
        help="""Determines which module is used to parse the notebook for endpoints and
            documentation. Valid module names include 'kernel_gateway.notebook_http.cell.parser'
            and 'kernel_gateway.notebook_http.swagger.parser'. (KG_CELL_PARSER env var)
            """
    )

    @default('cell_parser')
    def cell_parser_default(self):
        return os.getenv(self.cell_parser_env, 'kernel_gateway.notebook_http.cell.parser')

    # Intentionally not defining an env var option for a dict type
    comment_prefix = Dict({
        'scala': '//',
        None: '#'
    }, config=True, help='Maps kernel language to code comment syntax')

    allow_notebook_download_env = 'KG_ALLOW_NOTEBOOK_DOWNLOAD'
    allow_notebook_download = Bool(config=True,
        help="Optional API to download the notebook source code in notebook-http mode, defaults to not allow"
    )

    @default('allow_notebook_download')
    def allow_notebook_download_default(self):
        return os.getenv(self.allow_notebook_download_env, 'False') == 'True'

    static_path_env = 'KG_STATIC_PATH'
    static_path = Unicode(None, config=True, allow_none=True,
        help="Serve static files on disk in the given path as /public, defaults to not serve"
    )

    @default('static_path')
    def static_path_default(self):
        return os.getenv(self.static_path_env)

    def __init__(self, *args, **kwargs):
        super(NotebookHTTPPersonality, self).__init__(*args, **kwargs)
        # Import the module to use for cell endpoint parsing
        cell_parser_module = importlib.import_module(self.cell_parser)
        # Build the parser using the comment syntax for the notebook language
        func = getattr(cell_parser_module, 'create_parser')
        try:
            lang = self.parent.seed_source['metadata']['language_info']['name']
        except (AttributeError, KeyError):
            lang = None
        prefix = self.comment_prefix[lang]
        self.api_parser = func(parent=self, log=self.log,
                               comment_prefix=prefix,
                               notebook_cells=self.parent.seed_notebook.cells)

    def init_configurables(self):
        """Create a managed kernel pool"""
        self.kernel_pool = ManagedKernelPool(
            self.parent.prespawn_count,
            self.parent.kernel_manager
        )

    def create_request_handlers(self):
        """Create handlers and redefine them off of the base_url path. Assumes
        init_configurables() has already been called, and that the seed source
        was available there.
        """
        handlers = []
        # Register the NotebookDownloadHandler if configuration allows
        if self.allow_notebook_download:
            path = url_path_join('/', self.parent.base_url, r'/_api/source')
            self.log.info('Registering resource: {}, methods: (GET)'.format(path))
            handlers.append((
                path,
                NotebookDownloadHandler,
                {'path': self.parent.seed_uri}
            ))

        # Register a static path handler if configuration allows
        if self.static_path is not None:
            path = url_path_join('/', self.parent.base_url, r'/public/(.*)')
            self.log.info('Registering resource: {}, methods: (GET)'.format(path))
            handlers.append((
                path,
                tornado.web.StaticFileHandler,
                {'path': self.static_path}
            ))

        # Discover the notebook endpoints and their implementations
        endpoints = self.api_parser.endpoints(self.parent.kernel_manager.seed_source)
        response_sources = self.api_parser.endpoint_responses(self.parent.kernel_manager.seed_source)
        if len(endpoints) == 0:
            raise RuntimeError('No endpoints were discovered. Check your notebook to make sure your cells are annotated correctly.')

        # Cycle through the (endpoint_path, source) tuples and register their handlers
        for endpoint_path, verb_source_map in endpoints:
            parameterized_path = parameterize_path(endpoint_path)
            parameterized_path = url_path_join('/', self.parent.base_url, parameterized_path)
            self.log.info('Registering resource: {}, methods: ({})'.format(
                parameterized_path,
                list(verb_source_map.keys())
            ))
            response_source_map = response_sources[endpoint_path] if endpoint_path in response_sources else {}
            handler_args = { 'sources' : verb_source_map,
                'response_sources' : response_source_map,
                'kernel_pool' : self.kernel_pool,
                'kernel_name' : self.parent.kernel_manager.seed_kernelspec
            }
            handlers.append((parameterized_path, NotebookAPIHandler, handler_args))

        # Register the swagger API spec handler
        path = url_path_join('/', self.parent.base_url, r'/_api/spec/swagger.json')
        handlers.append((
            path,
            SwaggerSpecHandler, {
                'notebook_path' : self.parent.seed_uri,
                'source_cells': self.parent.seed_notebook.cells,
                'cell_parser' : self.api_parser
        }))
        self.log.info('Registering resource: {}, methods: (GET)'.format(path))

        # Add the 404 catch-all last
        handlers.append(default_base_handlers[-1])
        return handlers

    def should_seed_cell(self, code):
        """Determines whether the given code cell source should be executed when
        seeding a new kernel."""
        # seed cells that are uninvolved with the presented API
        return (not self.api_parser.is_api_cell(code) and not self.api_parser.is_api_response_cell(code))

    def shutdown(self):
        """Stop all kernels in the pool."""
        self.kernel_pool.shutdown()

def create_personality(*args, **kwargs):
    return NotebookHTTPPersonality(*args, **kwargs)
