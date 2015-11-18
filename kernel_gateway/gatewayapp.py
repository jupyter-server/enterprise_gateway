# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import os
import nbformat

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from traitlets import Unicode, Integer

from jupyter_core.application import JupyterApp
from jupyter_client.kernelspec import KernelSpecManager

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

import tornado
from tornado import httpserver
from tornado import web

from .services.kernels.handlers import default_handlers as default_kernel_handlers
from .services.kernelspecs.handlers import default_handlers as default_kernelspec_handlers
from .services.kernels.manager import SeedingMappingKernelManager
from .base.handlers import default_handlers as default_base_handlers

from notebook.utils import url_path_join

class KernelGatewayApp(JupyterApp):
    name = 'jupyter-kernel-gateway'
    description = '''
        Jupyter Kernel Gateway

        Provisions kernels and bridges Websocket communication
        to/from them.
    '''
    # Server IP / PORT binding
    port_env = 'KG_PORT'
    port = Integer(config=True,
        help="Port on which to listen (KG_PORT env var)"
    )
    def _port_default(self):
        return int(os.getenv(self.port_env, 8888))

    ip_env = 'KG_IP'
    ip = Unicode(config=True,
        help="IP address on which to listen (KG_IP env var)"
    )
    def _ip_default(self):
        return os.getenv(self.ip_env, '127.0.0.1')

    # Base URL
    base_url_env = 'KG_BASE_URL'
    base_url = Unicode(config=True,
        help='''The base path on which all API resources are mounted (KG_BASE_URL env var)''')
    def _base_url_default(self):
        return os.getenv(self.base_url_env, '/')

    # Token authorization
    auth_token_env = 'KG_AUTH_TOKEN'
    auth_token = Unicode(config=True,
        help='Authorization token required for all requests (KG_AUTH_TOKEN env var)'
    )
    def _auth_token_default(self):
        return os.getenv(self.auth_token_env, '')

    # CORS headers
    allow_credentials_env = 'KG_ALLOW_CREDENTIALS'
    allow_credentials = Unicode(config=True,
        help='Sets the Access-Control-Allow-Credentials header. (KG_ALLOW_CREDENTIALS env var)'
    )
    def _allow_credentials_default(self):
        return os.getenv(self.allow_credentials_env, '')

    allow_headers_env = 'KG_ALLOW_HEADERS'
    allow_headers = Unicode(config=True,
        help='Sets the Access-Control-Allow-Headers header. (KG_ALLOW_HEADERS env var)'
    )
    def _allow_headers_default(self):
        return os.getenv(self.allow_headers_env, '')

    allow_methods_env = 'KG_ALLOW_METHODS'
    allow_methods = Unicode(config=True,
        help='Sets the Access-Control-Allow-Methods header. (KG_ALLOW_METHODS env var)'
    )
    def _allow_methods_default(self):
        return os.getenv(self.allow_methods_env, '')

    allow_origin_env = 'KG_ALLOW_ORIGIN'
    allow_origin = Unicode(config=True,
        help='Sets the Access-Control-Allow-Origin header. (KG_ALLOW_ORIGIN env var)'
    )
    def _allow_origin_default(self):
        return os.getenv(self.allow_origin_env, '')

    expose_headers_env = 'KG_EXPOSE_HEADERS'
    expose_headers = Unicode(config=True,
        help='Sets the Access-Control-Expose-Headers header. (KG_EXPOSE_HEADERS env var)'
    )
    def _expose_headers_default(self):
        return os.getenv(self.expose_headers_env, '')

    max_age_env = 'KG_MAX_AGE'
    max_age = Unicode(config=True,
        help='Sets the Access-Control-Max-Age header. (KG_MAX_AGE env var)'
    )
    def _max_age_default(self):
        return os.getenv(self.max_age_env, '')

    max_kernels_env = 'KG_MAX_KERNELS'
    max_kernels = Integer(config=True,
        allow_none=True,
        help='Limits the number of kernel instances allowed to run by this gateway. (KG_MAX_KERNELS env var)'
    )
    def _max_kernels_default(self):
        val = os.getenv(self.max_kernels_env)
        return val if val is None else int(val)

    seed_uri_env = 'KG_SEED_URI'
    seed_uri = Unicode(config=True,
        allow_none=True,
        help='Runs the notebook (.ipynb) at the given URI on every kernel launched. (KG_SEED_URI env var)'
    )
    def _seed_uri_default(self):
        return os.getenv(self.seed_uri_env)

    prespawn_count_env = 'KG_PRESPAWN_COUNT'
    prespawn_count = Integer(config=True,
        default_value=None,
        allow_none=True,
        help='Number of kernels to prespawn using the default language. (KG_PRESPAWN_COUNT env var)'
    )
    def _prespawn_count_default(self):
        val = os.getenv(self.prespawn_count_env)
        return val if val is None else int(val)

    default_kernel_name_env = 'KG_DEFAULT_KERNEL_NAME'
    default_kernel_name = Unicode(config=True,
        help='''The default kernel name to use when spawning a kernel (KG_DEFAULT_KERNEL_NAME env var)''')
    def _default_kernel_name_default(self):
        # defaults to Jupyter's default kernel name on empty string
        return os.getenv(self.default_kernel_name_env, '')

    def _load_notebook(self, uri):
        '''
        Loads a local or remote notebook. Raises RuntimeError if no installed 
        kernel can handle the language specified in the notebook. Otherwise,
        returns the notebook object.
        '''
        parts = urlparse(self.seed_uri)

        if parts.netloc == '' or parts.netloc == 'file':
            # Local file
            with open(parts.path) as nb_fh:
                notebook = nbformat.read(nb_fh, 4)
        else:
            # Remote file
            import requests
            resp = requests.get(uri)
            resp.raise_for_status()
            notebook = nbformat.reads(resp.text, 4)

        # Error if no kernel spec can handle the language requested
        kernel_name = notebook['metadata']['kernelspec']['name']
        self.kernel_spec_manager.get_kernel_spec(kernel_name)

        return notebook

    def initialize(self, argv=None):
        '''
        Initialize base class, configurable Jupyter instances, the tornado web 
        app, and the tornado HTTP server.
        '''
        super(KernelGatewayApp, self).initialize(argv)
        self.init_configurables()
        self.init_webapp()
        self.init_http_server()

    def init_configurables(self):
        '''
        Initialize a kernel manager, optionally with notebook source to run
        on all launched kernels. Pre-spawn the requested number of kernels too.
        '''
        self.kernel_spec_manager = KernelSpecManager(parent=self)

        self.seed_notebook = None
        if self.seed_uri is not None:
            self.seed_notebook = self._load_notebook(self.seed_uri)

        self.kernel_manager = SeedingMappingKernelManager(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager
        )

        if self.prespawn_count is not None:
            if self.max_kernels is not None and self.prespawn_count > self.max_kernels:
                raise RuntimeError('cannot prespawn {}; more than max kernels {}'.format(
                    self.prespawn_count, self.max_kernels)
                )
            for _ in range(self.prespawn_count):
                self.kernel_manager.start_kernel()

    def init_webapp(self):
        '''
        Initialize tornado web application with kernel handlers. Put the kernel
        manager in settings to appease handlers that try to reference it there.
        Include additional options in settings as well.
        '''
        # Redefine handlers off the base_url path
        handlers = []
        for handler in (
            default_kernel_handlers + 
            default_kernelspec_handlers +
            default_base_handlers
        ):
            # Create a new handler pattern rooted at the base_url
            pattern = url_path_join(self.base_url, handler[0])
            # Some handlers take args, so retain those in addition to the
            # handler class ref
            new_handler = tuple([pattern] + list(handler[1:]))
            handlers.append(new_handler)

        self.web_app = web.Application(
            handlers=handlers,
            kernel_manager=self.kernel_manager,
            kernel_spec_manager=self.kernel_manager.kernel_spec_manager,
            kg_auth_token=self.auth_token,
            kg_allow_credentials=self.allow_credentials,
            kg_allow_headers=self.allow_headers,
            kg_allow_methods=self.allow_methods,
            kg_allow_origin=self.allow_origin,
            kg_expose_headers=self.expose_headers,
            kg_max_age=self.max_age,
            kg_max_kernels=self.max_kernels
        )

    def init_http_server(self):
        '''
        Initialize a HTTP server.
        '''
        self.http_server = httpserver.HTTPServer(self.web_app)
        self.http_server.listen(self.port, self.ip)

    def start(self):
        '''
        Start an IO loop for the application.
        '''
        super(KernelGatewayApp, self).start()
        self.log.info('The Jupyter Kernel Gateway is running at: http://{}:{}'.format(
            self.ip, self.port
        ))

        self.io_loop = ioloop.IOLoop.current()
        
        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.log.info("Interrupted...")

    def stop(self):
        '''
        Stop the HTTP server and IO loop associated with the application.
        '''
        def _stop():
            self.http_server.stop()
            self.io_loop.stop()
        self.io_loop.add_callback(_stop)

launch_instance = KernelGatewayApp.launch_instance
