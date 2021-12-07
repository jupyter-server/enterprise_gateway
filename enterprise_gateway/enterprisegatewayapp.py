# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Enterprise Gateway Jupyter application."""

import asyncio
import errno
import getpass
import logging
import os
import signal
import socket
import ssl
import sys
import time
import weakref

# Install the pyzmq ioloop. This has to be done before anything else from
# tornado is imported.
from zmq.eventloop import ioloop
ioloop.install()

from tornado import httpserver
from tornado import web
from tornado.log import enable_pretty_logging

from traitlets.config import Configurable
from jupyter_core.application import JupyterApp, base_aliases
from jupyter_client.kernelspec import KernelSpecManager
from notebook.notebookapp import random_ports
from notebook.utils import url_path_join

from ._version import __version__

from .base.handlers import default_handlers as default_base_handlers
from .services.api.handlers import default_handlers as default_api_handlers
from .services.kernels.handlers import default_handlers as default_kernel_handlers
from .services.kernelspecs.handlers import default_handlers as default_kernelspec_handlers
from .services.sessions.handlers import default_handlers as default_session_handlers

from .services.sessions.kernelsessionmanager import FileKernelSessionManager
from .services.sessions.sessionmanager import SessionManager
from .services.kernels.remotemanager import RemoteMappingKernelManager
from .services.kernelspecs import KernelSpecCache

from .mixins import EnterpriseGatewayConfigMixin


# Add additional command line aliases
aliases = dict(base_aliases)
aliases.update({
    'ip': 'EnterpriseGatewayApp.ip',
    'port': 'EnterpriseGatewayApp.port',
    'port_retries': 'EnterpriseGatewayApp.port_retries',
    'keyfile': 'EnterpriseGatewayApp.keyfile',
    'certfile': 'EnterpriseGatewayApp.certfile',
    'client-ca': 'EnterpriseGatewayApp.client_ca',
    'ssl_version': 'EnterpriseGatewayApp.ssl_version'
})


class EnterpriseGatewayApp(EnterpriseGatewayConfigMixin, JupyterApp):
    """
    Application that provisions Jupyter kernels and proxies HTTP/Websocket
    traffic to the kernels.

    - reads command line and environment variable settings
    - initializes managers and routes
    - creates a Tornado HTTP server
    - starts the Tornado event loop
    """
    name = 'jupyter-enterprise-gateway'
    version = __version__
    description = """
        Jupyter Enterprise Gateway

        Provisions remote Jupyter kernels and proxies HTTP/Websocket traffic to them.
    """

    # Also include when generating help options
    classes = [KernelSpecCache, FileKernelSessionManager, RemoteMappingKernelManager]

    # Enable some command line shortcuts
    aliases = aliases

    def initialize(self, argv=None):
        """Initializes the base class, configurable manager instances, the
        Tornado web app, and the tornado HTTP server.

        Parameters
        ----------
        argv
            Command line arguments
        """
        super(EnterpriseGatewayApp, self).initialize(argv)
        self.init_configurables()
        self.init_webapp()
        self.init_http_server()

    def init_configurables(self):
        """Initializes all configurable objects including a kernel manager, kernel
        spec manager, session manager, and personality.
        """
        self.kernel_spec_manager = KernelSpecManager(parent=self)

        # Only pass a default kernel name when one is provided. Otherwise,
        # adopt whatever default the kernel manager wants to use.
        kwargs = {}
        if self.default_kernel_name:
            kwargs['default_kernel_name'] = self.default_kernel_name

        self.kernel_spec_manager = self.kernel_spec_manager_class(
            parent=self,
        )

        self.kernel_spec_cache = self.kernel_spec_cache_class(
            parent=self,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs
        )

        self.kernel_manager = self.kernel_manager_class(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs
        )

        self.session_manager = SessionManager(
            log=self.log,
            kernel_manager=self.kernel_manager
        )

        self.kernel_session_manager = self.kernel_session_manager_class(
            parent=self,
            log=self.log,
            kernel_manager=self.kernel_manager,
            config=self.config,  # required to get command-line options visible
            **kwargs
        )

        # Attempt to start persisted sessions
        # Commented as part of https://github.com/jupyter/enterprise_gateway/pull/737#issuecomment-567598751
        # self.kernel_session_manager.start_sessions()

        self.contents_manager = None  # Gateways don't use contents manager

        self.init_dynamic_configs()

    def _create_request_handlers(self):
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
            pattern = url_path_join('/', self.base_url, handler[0])
            # Some handlers take args, so retain those in addition to the
            # handler class ref
            new_handler = tuple([pattern] + list(handler[1:]))
            handlers.append(new_handler)
        return handlers

    def init_webapp(self):
        """Initializes Tornado web application with uri handlers.

        Adds the various managers and web-front configuration values to the
        Tornado settings for reference by the handlers.
        """
        # Enable the same pretty logging the notebook uses
        enable_pretty_logging()

        # Configure the tornado logging level too
        logging.getLogger().setLevel(self.log_level)

        handlers = self._create_request_handlers()

        self.web_app = web.Application(
            handlers=handlers,
            kernel_manager=self.kernel_manager,
            session_manager=self.session_manager,
            contents_manager=self.contents_manager,
            kernel_spec_manager=self.kernel_spec_manager,
            kernel_spec_cache=self.kernel_spec_cache,
            eg_auth_token=self.auth_token,
            eg_allow_credentials=self.allow_credentials,
            eg_allow_headers=self.allow_headers,
            eg_allow_methods=self.allow_methods,
            eg_allow_origin=self.allow_origin,
            eg_expose_headers=self.expose_headers,
            eg_max_age=self.max_age,
            eg_max_kernels=self.max_kernels,
            eg_env_process_whitelist=self.env_process_whitelist,
            eg_env_whitelist=self.env_whitelist,
            eg_kernel_headers=self.kernel_headers,
            eg_list_kernels=self.list_kernels,
            eg_authorized_users=self.authorized_users,
            eg_unauthorized_users=self.unauthorized_users,
            # Also set the allow_origin setting used by notebook so that the
            # check_origin method used everywhere respects the value
            allow_origin=self.allow_origin,
            # Set base_url for use in request handlers
            base_url=self.base_url,
            # Always allow remote access (has been limited to localhost >= notebook 5.6)
            allow_remote_access=True,
            # setting ws_ping_interval value that can allow it to be modified for the purpose of toggling ping mechanism
            # for zmq web-sockets or increasing/decreasing web socket ping interval/timeouts.
            ws_ping_interval=self.ws_ping_interval * 1000
        )

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
        if self.ssl_version:
            ssl_options['ssl_version'] = self.ssl_version
        if not ssl_options:
            # None indicates no SSL config
            ssl_options = None
        else:
            ssl_options.setdefault('ssl_version', self.ssl_version_default_value)
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
                                                 xheaders=self.trust_xheaders,
                                                 ssl_options=ssl_options)

        for port in random_ports(self.port, self.port_retries + 1):
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
            self.log.critical('ERROR: the gateway server could not be started because '
                              'no available port could be found.')
            self.exit(1)

    def start(self):
        """Starts an IO loop for the application. """

        super(EnterpriseGatewayApp, self).start()

        self.log.info('Jupyter Enterprise Gateway {} is available at http{}://{}:{}'.format(
            EnterpriseGatewayApp.version, 's' if self.keyfile else '', self.ip, self.port
        ))
        # If impersonation is enabled, issue a warning message if the gateway user is not in unauthorized_users.
        if self.impersonation_enabled:
            gateway_user = getpass.getuser()
            if gateway_user.lower() not in self.unauthorized_users:
                self.log.warning("Impersonation is enabled and gateway user '{}' is NOT specified in the set of "
                                 "unauthorized users!  Kernels may execute as that user with elevated privileges.".
                                 format(gateway_user))

        self.io_loop = ioloop.IOLoop.current()

        if sys.platform != 'win32':
            signal.signal(signal.SIGHUP, signal.SIG_IGN)

        signal.signal(signal.SIGTERM, self._signal_stop)

        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.log.info("Interrupted...")
            # Ignore further interrupts (ctrl-c)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        finally:
            self.shutdown()

    def shutdown(self):
        """Shuts down all running kernels."""
        kids = self.kernel_manager.list_kernel_ids()
        for kid in kids:
            asyncio.get_event_loop().run_until_complete(self.kernel_manager.shutdown_kernel(kid, now=True))

    def stop(self):
        """
        Stops the HTTP server and IO loop associated with the application.
        """

        def _stop():
            self.http_server.stop()
            self.io_loop.stop()

        self.io_loop.add_callback(_stop)

    def _signal_stop(self, sig, frame):
        self.log.info("Received signal to terminate Enterprise Gateway.")
        self.io_loop.add_callback_from_signal(self.io_loop.stop)

    _last_config_update = int(time.time())
    _dynamic_configurables = {}

    def update_dynamic_configurables(self):
        """
        Called periodically, this checks the set of loaded configuration files for updates.
        If updates have been detected, reload the configuration files and update the list of
        configurables participating in dynamic updates.
        :return: True if updates were taken
        """
        updated = False
        configs = []
        for file in self.loaded_config_files:
            mod_time = int(os.path.getmtime(file))
            if mod_time > self._last_config_update:
                self.log.debug("Config file was updated: {}!".format(file))
                self._last_config_update = mod_time
                updated = True

        if updated:
            # If config changes are present, reload the config files.  This will also update
            # the Application's configuration, then update the config of each configurable
            # from the newly loaded values.

            self.load_config_file(self)

            for config_name, configurable in self._dynamic_configurables.items():
                # Since Application.load_config_file calls update_config on the Application, skip
                # the configurable registered with self (i.e., the application).
                if configurable is not self:
                    configurable.update_config(self.config)
                configs.append(config_name)

            self.log.info("Configuration file changes detected.  Instances for the following "
                          "configurables have been updated: {}".format(configs))
        return updated

    def add_dynamic_configurable(self, config_name, configurable):
        """
        Adds the configurable instance associated with the given name to the list of Configurables
        that can have their configurations updated when configuration file updates are detected.
        :param config_name: the name of the config within this application
        :param configurable: the configurable instance corresponding to that config
        """
        if not isinstance(configurable, Configurable):
            raise RuntimeError("'{}' is not a subclass of Configurable!".format(configurable))

        self._dynamic_configurables[config_name] = weakref.proxy(configurable)

    def init_dynamic_configs(self):
        """
        Initialize the set of configurables that should participate in dynamic updates.  We should
        also log that we're performing dynamic configuration updates, along with the list of CLI
        options - that are not privy to dynamic updates.
        :return:
        """
        if self.dynamic_config_interval > 0:
            self.add_dynamic_configurable('EnterpriseGatewayApp', self)
            self.add_dynamic_configurable('MappingKernelManager', self.kernel_manager)
            self.add_dynamic_configurable('KernelSpecManager', self.kernel_spec_manager)
            self.add_dynamic_configurable('KernelSessionManager', self.kernel_session_manager)

            self.log.info("Dynamic updates have been configured.  Checking every {} seconds.".
                          format(self.dynamic_config_interval))

            self.log.info("The following configuration options will not be subject to dynamic updates "
                          "(configured via CLI):")
            for config, options in self.cli_config.items():
                for option, value in options.items():
                    self.log.info("    '{}.{}': '{}'".format(config, option, value))

            if self.dynamic_config_poller is None:
                self.dynamic_config_poller = ioloop.PeriodicCallback(self.update_dynamic_configurables,
                                                                     self.dynamic_config_interval * 1000)
            self.dynamic_config_poller.start()


launch_instance = EnterpriseGatewayApp.launch_instance
