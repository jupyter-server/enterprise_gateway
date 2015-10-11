# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from traitlets import (
    Unicode, Integer
)

from jupyter_core.application import JupyterApp
# from jupyter_core.paths import jupyter_runtime_dir
from jupyter_client.kernelspec import KernelSpecManager

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

import tornado
from tornado import httpserver
from tornado import web
# from tornado.log import LogFormatter, app_log, access_log, gen_log

from .services.kernels.handlers import default_handlers as default_kernel_handlers
# import notebook.services.kernels.handlers as kernel_handlers
from notebook.services.kernels.kernelmanager import MappingKernelManager

class KernelGatewayApp(JupyterApp):
    name = 'jupyter-kernel-gateway'
    description = '''
        Jupyter Kernel Gateway

        Provisions kernels and bridges Websocket communication
        to/from them.
    '''

    port = Integer(8888, config=True,
        help="Port on which to listen"
    )

    ip = Unicode('0.0.0.0', config=True,
        help="IP address on which to listen"
    )

    auth_token = Unicode('', config=True,
        help='Authorization token required for all requests'
    )

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
            kg_auth_token=self.auth_token
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
