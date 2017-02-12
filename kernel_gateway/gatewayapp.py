# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Kernel Gateway Jupyter application."""

import os
import socket
import errno
import logging
import nbformat
import importlib

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse

from traitlets import Unicode, Integer, default, observe

from jupyter_core.application import JupyterApp, base_aliases
from jupyter_client.kernelspec import KernelSpecManager

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

from tornado import httpserver
from tornado import web
from tornado.log import enable_pretty_logging

from notebook.notebookapp import random_ports
from ._version import __version__
from .services.sessions.sessionmanager import SessionManager
from .services.activity.manager import ActivityManager
from .services.kernels.manager import SeedingMappingKernelManager

# Only present for generating help documentation
from .notebook_http import NotebookHTTPPersonality
from .jupyter_websocket import JupyterWebsocketPersonality

# Add additional command line aliases
aliases = dict(base_aliases)
aliases.update({
    'ip': 'KernelGatewayApp.ip',
    'port': 'KernelGatewayApp.port',
    'port_retries': 'KernelGatewayApp.port_retries',
    'api': 'KernelGatewayApp.api',
    'seed_uri': 'KernelGatewayApp.seed_uri',
    'keyfile': 'KernelGatewayApp.keyfile',
    'certfile': 'KernelGatewayApp.certfile',
    'client-ca': 'KernelGatewayApp.client_ca'
})


class KernelGatewayApp(JupyterApp):
    """Application that provisions Jupyter kernels and proxies HTTP/Websocket
    traffic to the kernels.

    - reads command line and environment variable settings
    - initializes managers and routes
    - creates a Tornado HTTP server
    - starts the Tornado event loop
    """
    name = 'jupyter-kernel-gateway'
    version = __version__
    description = """
        Jupyter Kernel Gateway

        Provisions Jupyter kernels and proxies HTTP/Websocket traffic
        to them.
    """

    # Also include when generating help options
    classes = [NotebookHTTPPersonality, JupyterWebsocketPersonality]
    # Enable some command line shortcuts
    aliases = aliases

    # Server IP / PORT binding
    port_env = 'KG_PORT'
    port_default_value = 8888
    port = Integer(port_default_value, config=True,
        help="Port on which to listen (KG_PORT env var)"
    )

    @default('port')
    def port_default(self):
        return int(os.getenv(self.port_env, self.port_default_value))

    port_retries_env = 'KG_PORT_RETRIES'
    port_retries_default_value = 50
    port_retries = Integer(port_retries_default_value, config=True,
        help="Number of ports to try if the specified port is not available (KG_PORT_RETRIES env var)"
    )

    @default('port_retries')
    def port_retries_default(self):
        return int(os.getenv(self.port_retries_env, self.port_retries_default_value))

    ip_env = 'KG_IP'
    ip_default_value = '127.0.0.1'
    ip = Unicode(ip_default_value, config=True,
        help="IP address on which to listen (KG_IP env var)"
    )

    @default('ip')
    def ip_default(self):
        return os.getenv(self.ip_env, self.ip_default_value)

    # Base URL
    base_url_env = 'KG_BASE_URL'
    base_url_default_value = '/'
    base_url = Unicode(base_url_default_value, config=True,
        help="""The base path for mounting all API resources (KG_BASE_URL env var)""")

    @default('base_url')
    def base_url_default(self):
        return os.getenv(self.base_url_env, self.base_url_default_value)

    # Token authorization
    auth_token_env = 'KG_AUTH_TOKEN'
    auth_token = Unicode(config=True,
        help='Authorization token required for all requests (KG_AUTH_TOKEN env var)'
    )

    @default('auth_token')
    def _auth_token_default(self):
        return os.getenv(self.auth_token_env, '')

    # CORS headers
    allow_credentials_env = 'KG_ALLOW_CREDENTIALS'
    allow_credentials = Unicode(config=True,
        help='Sets the Access-Control-Allow-Credentials header. (KG_ALLOW_CREDENTIALS env var)'
    )

    @default('allow_credentials')
    def allow_credentials_default(self):
        return os.getenv(self.allow_credentials_env, '')

    allow_headers_env = 'KG_ALLOW_HEADERS'
    allow_headers = Unicode(config=True,
        help='Sets the Access-Control-Allow-Headers header. (KG_ALLOW_HEADERS env var)'
    )

    @default('allow_headers')
    def allow_headers_default(self):
        return os.getenv(self.allow_headers_env, '')

    allow_methods_env = 'KG_ALLOW_METHODS'
    allow_methods = Unicode(config=True,
        help='Sets the Access-Control-Allow-Methods header. (KG_ALLOW_METHODS env var)'
    )

    @default('allow_methods')
    def allow_methods_default(self):
        return os.getenv(self.allow_methods_env, '')

    allow_origin_env = 'KG_ALLOW_ORIGIN'
    allow_origin = Unicode(config=True,
        help='Sets the Access-Control-Allow-Origin header. (KG_ALLOW_ORIGIN env var)'
    )

    @default('allow_origin')
    def allow_origin_default(self):
        return os.getenv(self.allow_origin_env, '')

    expose_headers_env = 'KG_EXPOSE_HEADERS'
    expose_headers = Unicode(config=True,
        help='Sets the Access-Control-Expose-Headers header. (KG_EXPOSE_HEADERS env var)'
    )

    @default('expose_headers')
    def expose_headers_default(self):
        return os.getenv(self.expose_headers_env, '')

    max_age_env = 'KG_MAX_AGE'
    max_age = Unicode(config=True,
        help='Sets the Access-Control-Max-Age header. (KG_MAX_AGE env var)'
    )

    @default('max_age')
    def max_age_default(self):
        return os.getenv(self.max_age_env, '')

    max_kernels_env = 'KG_MAX_KERNELS'
    max_kernels = Integer(None, config=True,
        allow_none=True,
        help='Limits the number of kernel instances allowed to run by this gateway. Unbounded by default. (KG_MAX_KERNELS env var)'
    )

    @default('max_kernels')
    def max_kernels_default(self):
        val = os.getenv(self.max_kernels_env)
        return val if val is None else int(val)

    seed_uri_env = 'KG_SEED_URI'
    seed_uri = Unicode(None, config=True,
        allow_none=True,
        help='Runs the notebook (.ipynb) at the given URI on every kernel launched. No seed by default. (KG_SEED_URI env var)'
    )

    @default('seed_uri')
    def seed_uri_default(self):
        return os.getenv(self.seed_uri_env)

    prespawn_count_env = 'KG_PRESPAWN_COUNT'
    prespawn_count = Integer(None, config=True,
        allow_none=True,
        help='Number of kernels to prespawn using the default language. No prespawn by default. (KG_PRESPAWN_COUNT env var)'
    )

    @default('prespawn_count')
    def prespawn_count_default(self):
        val = os.getenv(self.prespawn_count_env)
        return val if val is None else int(val)

    default_kernel_name_env = 'KG_DEFAULT_KERNEL_NAME'
    default_kernel_name = Unicode(config=True,
        help='Default kernel name when spawning a kernel (KG_DEFAULT_KERNEL_NAME env var)')

    @default('default_kernel_name')
    def default_kernel_name_default(self):
        # defaults to Jupyter's default kernel name on empty string
        return os.getenv(self.default_kernel_name_env, '')

    force_kernel_name_env = 'KG_FORCE_KERNEL_NAME'
    force_kernel_name = Unicode(config=True,
        help='Override any kernel name specified in a notebook or request (KG_FORCE_KERNEL_NAME env var)')

    @default('force_kernel_name')
    def force_kernel_name_default(self):
        return os.getenv(self.force_kernel_name_env, '')

    api_env = 'KG_API'
    api_default_value = 'kernel_gateway.jupyter_websocket'
    api = Unicode(api_default_value,
        config=True,
        help="""Controls which API to expose, that of a Jupyter notebook server, the seed
            notebook's, or one provided by another module, respectively using values
            'kernel_gateway.jupyter_websocket', 'kernel_gateway.notebook_http', or
            another fully qualified module name (KG_API env var)
            """
    )

    @default('api')
    def api_default(self):
        return os.getenv(self.api_env, self.api_default_value)

    @observe('api')
    def api_changed(self, event):
        try:
            self._load_api_module(event['new'])
        except ImportError:
            # re-raise with more sensible message to help the user
            raise ImportError('API module {} not found'.format(event['new']))

    certfile_env = 'KG_CERTFILE'
    certfile = Unicode(None, config=True, allow_none=True,
                       help="""The full path to an SSL/TLS certificate file. (KG_CERTFILE env var)""")

    @default('certfile')
    def certfile_default(self):
        return os.getenv(self.certfile_env)

    keyfile_env = 'KG_KEYFILE'
    keyfile = Unicode(None, config=True, allow_none=True,
                      help="""The full path to a private key file for usage with SSL/TLS. (KG_KEYFILE env var)""")

    @default('keyfile')
    def keyfile_default(self):
        return os.getenv(self.keyfile_env)

    client_ca_env = 'KG_CLIENT_CA'
    client_ca = Unicode(None, config=True, allow_none=True,
                        help="""The full path to a certificate authority certificate for SSL/TLS client authentication. (KG_CLIENT_CA env var)""")

    @default('client_ca')
    def client_ca_default(self):
        return os.getenv(self.client_ca_env)

    def _load_api_module(self, module_name):
        """Tries to import the given module name.

        Parameters
        ----------
        module_name: str
            Module name to import

        Returns
        -------
        module
            Module with the given name loaded using importlib.import_module
        """
        # some compatibility allowances
        if module_name == 'jupyter-websocket':
            module_name = 'kernel_gateway.jupyter_websocket'
        elif module_name == 'notebook-http':
            module_name = 'kernel_gateway.notebook_http'
        return importlib.import_module(module_name)

    def _load_notebook(self, uri):
        """Loads a notebook from the local filesystem or HTTP URL.

        Raises
        ------
        RuntimeError if there is no kernel spec matching the one specified in
        the notebook or forced via configuration.

        Returns
        -------
        object
            Notebook object from nbformat
        """
        parts = urlparse(uri)

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
        kernel_name = self.force_kernel_name if self.force_kernel_name \
            else notebook['metadata']['kernelspec']['name']
        self.kernel_spec_manager.get_kernel_spec(kernel_name)

        return notebook

    def initialize(self, argv=None):
        """Initializes the base class, configurable manager instances, the
        Tornado web app, and the tornado HTTP server.

        Parameters
        ----------
        argv
            Command line arguments
        """
        super(KernelGatewayApp, self).initialize(argv)
        self.init_configurables()
        self.init_webapp()
        self.init_http_server()

    def init_configurables(self):
        """Initializes all configurable objects including a kernel manager, kernel
        spec manager, session manager, activity manager, and personality.

        Any kernel pool configured by the personality will be its responsibility
        to shut down.

        Optionally, loads a notebook and prespawns the configured number of
        kernels.
        """
        self.kernel_spec_manager = KernelSpecManager(parent=self)

        self.seed_notebook = None
        if self.seed_uri is not None:
            # Note: must be set before instantiating a SeedingMappingKernelManager
            self.seed_notebook = self._load_notebook(self.seed_uri)

        # Only pass a default kernel name when one is provided. Otherwise,
        # adopt whatever default the kernel manager wants to use.
        kwargs = {}
        if self.default_kernel_name:
            kwargs['default_kernel_name'] = self.default_kernel_name
        self.kernel_manager = SeedingMappingKernelManager(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs
        )

        self.activity_manager = ActivityManager(
            parent=self,
            log=self.log,
            kernel_manager=self.kernel_manager
        )

        self.session_manager = SessionManager(
            log=self.log,
            kernel_manager=self.kernel_manager
        )
        self.contents_manager = None

        if self.prespawn_count:
            if self.max_kernels and self.prespawn_count > self.max_kernels:
                raise RuntimeError('cannot prespawn {}; more than max kernels {}'.format(
                    self.prespawn_count, self.max_kernels)
                )

        api_module = self._load_api_module(self.api)
        func = getattr(api_module, 'create_personality')
        self.personality = func(parent=self, log=self.log)

        self.personality.init_configurables()

    def init_webapp(self):
        """Initializes Tornado web application with uri handlers.

        Adds the various managers and web-front configuration values to the
        Tornado settings for reference by the handlers.
        """
        # Enable the same pretty logging the notebook uses
        enable_pretty_logging()

        # Configure the tornado logging level too
        logging.getLogger().setLevel(self.log_level)

        handlers = self.personality.create_request_handlers()

        self.web_app = web.Application(
            handlers=handlers,
            activity_manager=self.activity_manager,
            kernel_manager=self.kernel_manager,
            session_manager=self.session_manager,
            contents_manager=self.contents_manager,
            kernel_spec_manager=self.kernel_manager.kernel_spec_manager,
            kg_auth_token=self.auth_token,
            kg_allow_credentials=self.allow_credentials,
            kg_allow_headers=self.allow_headers,
            kg_allow_methods=self.allow_methods,
            kg_allow_origin=self.allow_origin,
            kg_expose_headers=self.expose_headers,
            kg_max_age=self.max_age,
            kg_max_kernels=self.max_kernels,
            kg_api=self.api,
            kg_personality=self.personality,
            # Also set the allow_origin setting used by notebook so that the
            # check_origin method used everywhere respects the value
            allow_origin=self.allow_origin
        )

        # promote the current personality's "config" tagged traitlet values to webapp settings
        for trait_name, trait_value in self.personality.class_traits(config=True).items():
            kg_name = 'kg_' + trait_name
            # a personality's traitlets may not overwrite the kernel gateway's
            if kg_name not in self.web_app.settings:
                self.web_app.settings[kg_name] = trait_value.get(obj=self.personality)
            else:
                self.log.warning('The personality trait name, %s, conflicts with a kernel gateway trait.', trait_name)

    def _build_ssl_options(self):
        """Build a dictionary of SSL options for the tornado HTTP server.

        Taken directly from jupyter/notebook code.
        """
        ssl_options = {}
        if self.certfile:
            ssl_options['certfile'] = self.certfile
        if self.keyfile:
            ssl_options['keyfile'] = self.keyfile
        if self.client_ca:
            ssl_options['ca_certs'] = self.client_ca
        if not ssl_options:
            # None indicates no SSL config
            ssl_options = None
        else:
            # SSL may be missing, so only import it if it's to be used
            import ssl
            # Disable SSLv3 by default, since its use is discouraged.
            ssl_options.setdefault('ssl_version', ssl.PROTOCOL_TLSv1)
            if ssl_options.get('ca_certs', False):
                ssl_options.setdefault('cert_reqs', ssl.CERT_REQUIRED)

        return ssl_options

    def init_http_server(self):
        """Initializes a HTTP server for the Tornado web application on the
        configured interface and port.

        Tries to find an open port if the one configured is not available using
        the same logic as the Jupyer Notebook server.
        """
        ssl_options = self._build_ssl_options()
        self.http_server = httpserver.HTTPServer(self.web_app,
                                                 ssl_options=ssl_options)

        for port in random_ports(self.port, self.port_retries+1):
            try:
                self.http_server.listen(port, self.ip)
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:
                    self.log.info('The port %i is already in use, trying another port.' % port)
                    continue
                elif e.errno in (errno.EACCES, getattr(errno, 'WSAEACCES', errno.EACCES)):
                    self.log.warning("Permission to listen on port %i denied" % port)
                    continue
                else:
                    raise
            else:
                self.port = port
                break
        else:
            self.log.critical('ERROR: the notebook server could not be started because '
                              'no available port could be found.')
            self.exit(1)

    def start(self):
        """Starts an IO loop for the application."""
        super(KernelGatewayApp, self).start()
        self.log.info('Jupyter Kernel Gateway at http{}://{}:{}'.format(
            's' if self.keyfile else '', self.ip, self.port
        ))

        self.io_loop = ioloop.IOLoop.current()

        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.log.info("Interrupted...")
        finally:
            self.shutdown()

    def stop(self):
        """
        Stops the HTTP server and IO loop associated with the application.
        """
        def _stop():
            self.http_server.stop()
            self.io_loop.stop()
        self.io_loop.add_callback(_stop)

    def shutdown(self):
        """Stop all kernels in the pool."""
        self.personality.shutdown()


launch_instance = KernelGatewayApp.launch_instance
