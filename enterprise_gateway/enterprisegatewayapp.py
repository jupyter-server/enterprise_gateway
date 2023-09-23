# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Enterprise Gateway Jupyter application."""

import asyncio
import errno
import getpass
import logging
import os
import signal
import ssl
import sys
import time
import weakref
from typing import ClassVar, List, Optional

from jupyter_client.kernelspec import KernelSpecManager
from jupyter_core.application import JupyterApp, base_aliases
from jupyter_server.serverapp import random_ports
from jupyter_server.utils import url_path_join
from tornado import httpserver, web
from tornado.log import enable_pretty_logging
from traitlets.config import Configurable
from zmq.eventloop import ioloop

from ._version import __version__
from .base.handlers import default_handlers as default_base_handlers
from .mixins import EnterpriseGatewayConfigMixin
from .services.api.handlers import default_handlers as default_api_handlers
from .services.kernels.handlers import default_handlers as default_kernel_handlers
from .services.kernels.remotemanager import RemoteMappingKernelManager
from .services.kernelspecs import KernelSpecCache
from .services.kernelspecs.handlers import default_handlers as default_kernelspec_handlers
from .services.sessions.handlers import default_handlers as default_session_handlers
from .services.sessions.kernelsessionmanager import (
    FileKernelSessionManager,
    WebhookKernelSessionManager,
)
from .services.sessions.sessionmanager import SessionManager

try:
    from jupyter_server.auth.authorizer import AllowAllAuthorizer
except ImportError:
    AllowAllAuthorizer = object

# Add additional command line aliases
aliases = dict(base_aliases)
aliases.update(
    {
        "ip": "EnterpriseGatewayApp.ip",
        "port": "EnterpriseGatewayApp.port",
        "port_retries": "EnterpriseGatewayApp.port_retries",
        "keyfile": "EnterpriseGatewayApp.keyfile",
        "certfile": "EnterpriseGatewayApp.certfile",
        "client-ca": "EnterpriseGatewayApp.client_ca",
        "ssl_version": "EnterpriseGatewayApp.ssl_version",
    }
)


class EnterpriseGatewayApp(EnterpriseGatewayConfigMixin, JupyterApp):
    """
    Application that provisions Jupyter kernels and proxies HTTP/Websocket
    traffic to the kernels.

    - reads command line and environment variable settings
    - initializes managers and routes
    - creates a Tornado HTTP server
    - starts the Tornado event loop
    """

    name = "jupyter-enterprise-gateway"
    version = __version__
    description = """
        Jupyter Enterprise Gateway

        Provisions remote Jupyter kernels and proxies HTTP/Websocket traffic to them.
    """

    # Also include when generating help options
    classes: ClassVar = [
        KernelSpecCache,
        FileKernelSessionManager,
        WebhookKernelSessionManager,
        RemoteMappingKernelManager,
    ]

    # Enable some command line shortcuts
    aliases = aliases

    def initialize(self, argv: Optional[List[str]] = None) -> None:
        """Initializes the base class, configurable manager instances, the
        Tornado web app, and the tornado HTTP server.

        Parameters
        ----------
        argv
            Command line arguments
        """
        super().initialize(argv)
        self.init_configurables()
        self.init_webapp()
        self.init_http_server()

    def init_configurables(self) -> None:
        """Initializes all configurable objects including a kernel manager, kernel
        spec manager, session manager, and personality.
        """
        self.kernel_spec_manager = KernelSpecManager(parent=self)

        self.kernel_spec_manager = self.kernel_spec_manager_class(
            parent=self,
        )

        self.kernel_spec_cache = self.kernel_spec_cache_class(
            parent=self, kernel_spec_manager=self.kernel_spec_manager
        )

        # Only pass a default kernel name when one is provided. Otherwise,
        # adopt whatever default the kernel manager wants to use.
        kwargs = {}
        if self.default_kernel_name:
            kwargs["default_kernel_name"] = self.default_kernel_name

        self.kernel_manager = self.kernel_manager_class(
            parent=self,
            log=self.log,
            connection_dir=self.runtime_dir,
            kernel_spec_manager=self.kernel_spec_manager,
            **kwargs,
        )

        self.session_manager = SessionManager(log=self.log, kernel_manager=self.kernel_manager)

        self.kernel_session_manager = self.kernel_session_manager_class(
            parent=self,
            log=self.log,
            kernel_manager=self.kernel_manager,
            config=self.config,  # required to get command-line options visible
        )

        # For B/C purposes, check if session persistence is enabled.  If so, and availability
        # mode is not enabled, go ahead and default availability mode to 'multi-instance'.
        if self.kernel_session_manager.enable_persistence:
            if self.availability_mode is None:
                self.availability_mode = EnterpriseGatewayConfigMixin.AVAILABILITY_REPLICATION
                self.log.info(
                    f"Kernel session persistence is enabled but availability mode is not.  "
                    f"Setting EnterpriseGatewayApp.availability_mode to '{self.availability_mode}'."
                )
        else:
            # Persistence is not enabled, check if availability_mode is configured and, if so,
            # auto-enable persistence
            if self.availability_mode is not None:
                self.kernel_session_manager.enable_persistence = True
                self.log.info(
                    f"Availability mode is set to '{self.availability_mode}' yet kernel session "
                    "persistence is not enabled.  Enabling kernel session persistence."
                )

        # If we're using single-instance availability, attempt to start persisted sessions
        if self.availability_mode == EnterpriseGatewayConfigMixin.AVAILABILITY_STANDALONE:
            self.kernel_session_manager.start_sessions()

        self.contents_manager = None  # Gateways don't use contents manager

        self.init_dynamic_configs()

    def _create_request_handlers(self) -> List[tuple]:
        """Create default Jupyter handlers and redefine them off of the
        base_url path. Assumes init_configurables() has already been called.
        """
        handlers = []

        # append tuples for the standard kernel gateway endpoints
        for handler in (
            default_api_handlers
            + default_kernel_handlers
            + default_kernelspec_handlers
            + default_session_handlers
            + default_base_handlers
        ):
            # Create a new handler pattern rooted at the base_url
            pattern = url_path_join("/", self.base_url, handler[0])
            # Some handlers take args, so retain those in addition to the
            # handler class ref
            new_handler = (pattern, *list(handler[1:]))
            if self.authorized_origin:
                self.__add_authorized_hostname_match(new_handler)

            handlers.append(new_handler)
        return handlers

    def __add_authorized_hostname_match(self, handler: tuple) -> None:
        base_prepare = handler[1].prepare
        authorized_hostname = self.authorized_origin

        def wrapped_prepare(self):
            ssl_cert = self.request.get_ssl_certificate()
            try:
                ssl.match_hostname(ssl_cert, authorized_hostname)
            except ssl.SSLCertVerificationError:
                raise web.HTTPError(403, "Forbidden") from None
            base_prepare(self)

        handler[1].prepare = wrapped_prepare

    def init_webapp(self) -> None:
        """Initializes Tornado web application with uri handlers.

        Adds the various managers and web-front configuration values to the
        Tornado settings for reference by the handlers.
        """
        # Enable the same pretty logging the server uses
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
            eg_inherited_envs=self.inherited_envs,
            eg_client_envs=self.client_envs,
            eg_kernel_headers=self.kernel_headers,
            eg_list_kernels=self.list_kernels,
            eg_authorized_users=self.authorized_users,
            eg_unauthorized_users=self.unauthorized_users,
            # Also set the allow_origin setting used by jupyter_server so that the
            # check_origin method used everywhere respects the value
            allow_origin=self.allow_origin,
            # Set base_url for use in request handlers
            base_url=self.base_url,
            # Always allow remote access (has been limited to localhost >= notebook 5.6)
            allow_remote_access=True,
            # setting ws_ping_interval value that can allow it to be modified for the purpose of toggling ping mechanism
            # for zmq web-sockets or increasing/decreasing web socket ping interval/timeouts.
            ws_ping_interval=self.ws_ping_interval * 1000,
            # Add a pass-through authorizer for now
            authorizer=AllowAllAuthorizer(),
        )

    def _build_ssl_options(self) -> Optional[ssl.SSLContext]:
        """Build an SSLContext for the tornado HTTP server."""
        if not any((self.certfile, self.keyfile, self.client_ca)):
            # None indicates no SSL config
            return None

        ssl_context = ssl.SSLContext(protocol=self.ssl_version or self.ssl_version_default_value)
        if self.certfile:
            ssl_context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
        if self.client_ca:
            ssl_context.load_verify_locations(cafile=self.client_ca)
            ssl_context.verify_mode = ssl.CERT_REQUIRED

        return ssl_context

    def init_http_server(self) -> None:
        """Initializes an HTTP server for the Tornado web application on the
        configured interface and port.

        Tries to find an open port if the one configured is not available using
        the same logic as the Jupyter Notebook server.
        """
        ssl_options = self._build_ssl_options()
        self.http_server = httpserver.HTTPServer(
            self.web_app, xheaders=self.trust_xheaders, ssl_options=ssl_options
        )

        for port in random_ports(self.port, self.port_retries + 1):
            try:
                self.http_server.listen(port, self.ip)
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    self.log.info("The port %i is already in use, trying another port." % port)
                    continue
                elif e.errno in (errno.EACCES, getattr(errno, "WSAEACCES", errno.EACCES)):
                    self.log.warning("Permission to listen on port %i denied" % port)
                    continue
                else:
                    raise
            else:
                self.port = port
                break
        else:
            self.log.critical(
                "ERROR: the gateway server could not be started because "
                "no available port could be found."
            )
            self.exit(1)

    def start(self) -> None:
        """Starts an IO loop for the application."""

        super().start()

        self.log.info(
            "Jupyter Enterprise Gateway {} is available at http{}://{}:{}".format(
                EnterpriseGatewayApp.version, "s" if self.keyfile else "", self.ip, self.port
            )
        )
        # If impersonation is enabled, issue a warning message if the gateway user is not in unauthorized_users.
        if self.impersonation_enabled:
            gateway_user = getpass.getuser()
            if gateway_user.lower() not in self.unauthorized_users:
                self.log.warning(
                    "Impersonation is enabled and gateway user '{}' is NOT specified in the set of "
                    "unauthorized users!  Kernels may execute as that user with elevated privileges.".format(
                        gateway_user
                    )
                )

        self.io_loop = ioloop.IOLoop.current()

        if sys.platform != "win32":
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

    def shutdown(self) -> None:
        """Shuts down all running kernels."""
        self.log.info("Jupyter Enterprise Gateway is shutting down all running kernels")
        kids = self.kernel_manager.list_kernel_ids()
        for kid in kids:
            try:
                asyncio.get_event_loop().run_until_complete(
                    self.kernel_manager.shutdown_kernel(kid, now=True)
                )
            except Exception as ex:
                self.log.warning(f"Failed to shut down kernel {kid}: {ex}")
        self.log.info("Shut down complete")

    def stop(self) -> None:
        """
        Stops the HTTP server and IO loop associated with the application.
        """

        def _stop():
            self.http_server.stop()
            self.io_loop.stop()

        self.io_loop.add_callback(_stop)

    def _signal_stop(self, sig, frame) -> None:
        self.log.info("Received signal to terminate Enterprise Gateway.")
        self.io_loop.add_callback_from_signal(self.io_loop.stop)

    _last_config_update = int(time.time())
    _dynamic_configurables: ClassVar = {}

    def update_dynamic_configurables(self) -> bool:
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
                self.log.debug(f"Config file was updated: {file}!")
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

            self.log.info(
                "Configuration file changes detected.  Instances for the following "
                f"configurables have been updated: {configs}"
            )
        return updated

    def add_dynamic_configurable(self, config_name: str, configurable: Configurable) -> None:
        """
        Adds the configurable instance associated with the given name to the list of Configurables
        that can have their configurations updated when configuration file updates are detected.
        :param config_name: the name of the config within this application
        :param configurable: the configurable instance corresponding to that config
        """
        if not isinstance(configurable, Configurable):
            msg = f"'{configurable}' is not a subclass of Configurable!"
            raise RuntimeError(msg)

        self._dynamic_configurables[config_name] = weakref.proxy(configurable)

    def init_dynamic_configs(self) -> None:
        """
        Initialize the set of configurables that should participate in dynamic updates.  We should
        also log that we're performing dynamic configuration updates, along with the list of CLI
        options - that are not privy to dynamic updates.
        :return:
        """
        if self.dynamic_config_interval > 0:
            self.add_dynamic_configurable("EnterpriseGatewayApp", self)
            self.add_dynamic_configurable("MappingKernelManager", self.kernel_manager)
            self.add_dynamic_configurable("KernelSpecManager", self.kernel_spec_manager)
            self.add_dynamic_configurable("KernelSessionManager", self.kernel_session_manager)

            self.log.info(
                "Dynamic updates have been configured.  Checking every {} seconds.".format(
                    self.dynamic_config_interval
                )
            )

            self.log.info(
                "The following configuration options will not be subject to dynamic updates "
                "(configured via CLI):"
            )
            for config, options in self.cli_config.items():
                for option, value in options.items():
                    self.log.info(f"    '{config}.{option}': '{value}'")

            if self.dynamic_config_poller is None:
                self.dynamic_config_poller = ioloop.PeriodicCallback(
                    self.update_dynamic_configurables, self.dynamic_config_interval * 1000
                )
            self.dynamic_config_poller.start()


launch_instance = EnterpriseGatewayApp.launch_instance
