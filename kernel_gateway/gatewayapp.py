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

import notebook.services.kernels.handlers as kernel_handlers
from notebook.services.kernels.kernelmanager import MappingKernelManager

class KernelGatewayApp(JupyterApp):
    name = 'jupyter-kernel-gateway'
    description = '''
        Jupyter Kernel Gateway

        Provisions kernels and bridges Websocket communication
        to/from them.
    '''

    port = Integer(8888, config=True,
        help="The port the notebook server will listen on."
    )

    ip = Unicode('0.0.0.0', config=True,
        help="The IP address the notebook server will listen on."
    )

    def initialize(self, argv=None):
        super(KernelGatewayApp, self).initialize(argv)
        self.init_configurables()
        self.init_webapp()
        self.init_http_server()

    def init_configurables(self):
        '''
        Initialize cluster manager, kernel manager.
        '''
        self.kernel_manager = MappingKernelManager(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=KernelSpecManager(parent=self)
        )

    def init_webapp(self):
        '''
        Initialize tornado web application.
        '''
        self.web_app = web.Application(
            handlers=kernel_handlers.default_handlers,
            kernel_manager=self.kernel_manager
        )

    def init_http_server(self):
        self.http_server = httpserver.HTTPServer(self.web_app)
        self.http_server.listen(self.port, self.ip)

    def start(self):
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
        def _stop():
            self.http_server.stop()
            self.io_loop.stop()
        self.io_loop.add_callback(_stop)

launch_instance = KernelGatewayApp.launch_instance
