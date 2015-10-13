# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import os

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
from notebook.services.kernels.kernelmanager import MappingKernelManager

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
        Initialize a kernel manager.
        '''
        self.kernel_manager = MappingKernelManager(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=KernelSpecManager(parent=self)
        )

    def init_webapp(self):
        '''
        Initialize tornado web application with kernel handlers. Put the kernel
        manager in settings to appease handlers that try to reference it there.
        Include additional options in settings as well.
        '''
        self.web_app = web.Application(
            handlers=default_kernel_handlers,
            kernel_manager=self.kernel_manager,
            kg_auth_token=self.auth_token,
            kg_allow_credentials=self.allow_credentials,
            kg_allow_headers=self.allow_headers,
            kg_allow_methods=self.allow_methods,
            kg_allow_origin=self.allow_origin,
            kg_expose_headers=self.expose_headers,
            kg_max_age=self.max_age
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
