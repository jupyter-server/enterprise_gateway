# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel CRUD and communication."""
import json
import os

import tornado
import jupyter_server.services.kernels.handlers as jupyter_server_handlers
from jupyter_client.jsonutil import date_default
from tornado import web
from functools import partial
from ...mixins import CORSMixin, JSONErrorsMixin, KernelEnvMixin, TokenAuthorizationMixin


class MainKernelHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        KernelEnvMixin,
                        jupyter_server_handlers.MainKernelHandler):
    """Extends the jupyter_server main kernel handler with token auth, CORS, and
    JSON errors.
    """



    async def post(self):
        """Overrides the super class method to manage env in the request body.

        Max kernel limits are now enforced in RemoteMappingKernelManager.start_kernel().

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if either max kernel limit is reached (total or per user, if configured)
        """
        max_kernels = self.settings['eg_max_kernels']
        if max_kernels is not None:
            km = self.settings['kernel_manager']
            kernels = km.list_kernels()
            if len(kernels) >= max_kernels:
                raise tornado.web.HTTPError(403, 'Resource Limit')

        # Try to get env vars from the request body
        model = self.get_json_body()
        if model is not None and 'env' in model:
            if not isinstance(model['env'], dict):
                raise tornado.web.HTTPError(400)

            env = {
                # always inherit PATH from the gateway env
                **{'PATH': os.getenv('PATH', '')},
                # inherit vars from the gateway env if var name in self.env_inherit
                **{k:v for k, v in os.environ.items() if k in self.kernel_env_inherit},
                # forward vars from request env if var name starts with KERNEL_ or in self.env_forward
                **{k:v for k, v in model['env'].items() if k.startswith('KERNEL_') or k in self.kernel_env_keys},
            }

            # If kernel_headers are configured, fetch each of those and include in start request
            kernel_headers = {}
            missing_headers = []
            kernel_header_names = self.settings['eg_kernel_headers']
            for name in kernel_header_names:
                if name:  # Ignore things like empty strings
                    value = self.request.headers.get(name)
                    if value:
                        kernel_headers[name] = value
                    else:
                        missing_headers.append(name)

            if len(missing_headers):
                self.log.warning("The following headers specified in 'kernel-headers' were not found: {}".
                                 format(missing_headers))

            # No way to override the call to start_kernel on the kernel manager
            # so do a temporary partial (ugh)
            orig_start = self.kernel_manager.start_kernel
            self.kernel_manager.start_kernel = partial(self.kernel_manager.start_kernel,
                                                       env=env,
                                                       kernel_headers=kernel_headers)
            try:
                await super(MainKernelHandler, self).post()
            finally:
                self.kernel_manager.start_kernel = orig_start
        else:
            await super(MainKernelHandler, self).post()

    async def get(self):
        """Overrides the super class method to honor the kernel listing
        configuration setting.

        Allows the request to reach the super class if listing is enabled.

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if kernel listing is disabled
        """
        if not self.settings.get('eg_list_kernels'):
            raise tornado.web.HTTPError(403, 'Forbidden')
        else:
            await super(MainKernelHandler, self).get()

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()


class KernelHandler(TokenAuthorizationMixin,
                    CORSMixin,
                    JSONErrorsMixin,
                    jupyter_server_handlers.KernelHandler):
    """Extends the jupyter_server kernel handler with token auth, CORS, and
    JSON errors.
    """

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()

    @web.authenticated
    def get(self, kernel_id):
        km = self.kernel_manager
        km.check_kernel_id(kernel_id)
        model = km.kernel_model(kernel_id)
        self.finish(json.dumps(model, default=date_default))


default_handlers = []
for path, cls in jupyter_server_handlers.default_handlers:
    if cls.__name__ in globals():
        # Use the same named class from here if it exists
        default_handlers.append((path, globals()[cls.__name__]))
    else:
        # Gen a new type with CORS and token auth
        bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
        default_handlers.append((path, type(cls.__name__, bases, {})))
