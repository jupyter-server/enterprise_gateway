# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel CRUD and communication."""
import json
import os

import tornado
import notebook.services.kernels.handlers as notebook_handlers
from jupyter_client.jsonutil import date_default
from tornado import gen, web
from functools import partial
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin


class MainKernelHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        notebook_handlers.MainKernelHandler):
    """Extends the notebook main kernel handler with token auth, CORS, and
    JSON errors.
    """

    @property
    def env_whitelist(self):
        return self.settings['eg_env_whitelist']

    @property
    def env_process_whitelist(self):
        return self.settings['eg_env_process_whitelist']

    @gen.coroutine
    def post(self):
        """Overrides the super class method to honor the max number of allowed
        kernels configuration setting and to support custom kernel environment
        variables for every request.

        Delegates the request to the super class implementation if no limit is
        set or if the maximum is not reached. Otherwise, responds with an
        error.

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if the limit is reached
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
            # Start with the PATH from the current env. Do not provide the entire environment
            # which might contain server secrets that should not be passed to kernels.
            env = {'PATH': os.getenv('PATH', '')}
            # Whitelist environment variables from current process environment
            env.update({key: value for key, value in os.environ.items()
                        if key in self.env_process_whitelist})
            # Whitelist KERNEL_* args and those allowed by configuration from client
            env.update({key: value for key, value in model['env'].items()
                        if key.startswith('KERNEL_') or key in self.env_whitelist})
            # No way to override the call to start_kernel on the kernel manager
            # so do a temporary partial (ugh)
            orig_start = self.kernel_manager.start_kernel
            self.kernel_manager.start_kernel = partial(self.kernel_manager.start_kernel, env=env)
            try:
                yield super(MainKernelHandler, self).post()
            finally:
                self.kernel_manager.start_kernel = orig_start
        else:
            yield super(MainKernelHandler, self).post()

    def get(self):
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
            super(MainKernelHandler, self).get()

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()


class KernelHandler(TokenAuthorizationMixin,
                    CORSMixin,
                    JSONErrorsMixin,
                    notebook_handlers.KernelHandler):
    """Extends the notebook kernel handler with token auth, CORS, and
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
for path, cls in notebook_handlers.default_handlers:
    if cls.__name__ in globals():
        # Use the same named class from here if it exists
        default_handlers.append((path, globals()[cls.__name__]))
    else:
        # Gen a new type with CORS and token auth
        bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
        default_handlers.append((path, type(cls.__name__, bases, {})))
