# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel CRUD and communication."""
import json
import os
from functools import partial

import jupyter_server.services.kernels.handlers as jupyter_server_handlers
import tornado
from jupyter_client.jsonutil import date_default
from jupyter_server.utils import ensure_async
from tornado import web

from ...mixins import CORSMixin, JSONErrorsMixin, TokenAuthorizationMixin
from ..kernels.remotemanager import UNIVERSAL_TENANT_ID


class MainKernelHandler(
    TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, jupyter_server_handlers.MainKernelHandler
):
    """Extends the jupyter_server main kernel handler with token auth, CORS, and
    JSON errors.
    """

    @property
    def env_whitelist(self):
        return self.settings["eg_env_whitelist"]

    @property
    def env_process_whitelist(self):
        return self.settings["eg_env_process_whitelist"]

    async def post(self):
        """Overrides the super class method to manage env in the request body.

        Max kernel limits are now enforced in RemoteMappingKernelManager.start_kernel().

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if either max kernel limit is reached (total or per user, if configured)
        """
        max_kernels = self.settings["eg_max_kernels"]
        if max_kernels is not None:
            km = self.settings["kernel_manager"]
            kernels = km.list_kernels()
            if len(kernels) >= max_kernels:
                raise tornado.web.HTTPError(403, "Resource Limit")

        tenant_id = UNIVERSAL_TENANT_ID
        env = {}
        # Try to get tenant_id and env vars from the request body
        model = self.get_json_body()
        if model is not None:
            tenant_id = model.get("tenant_id", UNIVERSAL_TENANT_ID)
            if "env" in model:
                if not isinstance(model["env"], dict):
                    raise tornado.web.HTTPError(400)
                # Start with the PATH from the current env. Do not provide the entire environment
                # which might contain server secrets that should not be passed to kernels.
                env = {"PATH": os.getenv("PATH", "")}
                # Whitelist environment variables from current process environment
                env.update(
                    {
                        key: value
                        for key, value in os.environ.items()
                        if key in self.env_process_whitelist
                    }
                )
                # Whitelist KERNEL_* args and those allowed by configuration from client.  If all
                # envs are requested, just use the keys from the payload.
                env_whitelist = self.env_whitelist
                if env_whitelist == ["*"]:
                    env_whitelist = model["env"].keys()
                env.update(
                    {
                        key: value
                        for key, value in model["env"].items()
                        if key.startswith("KERNEL_") or key in env_whitelist
                    }
                )

            # Set KERNEL_TENANT_ID.  If already present, we override with the value in the body
            env["KERNEL_TENANT_ID"] = tenant_id
            # If kernel_headers are configured, fetch each of those and include in start request
            kernel_headers = {}
            missing_headers = []
            kernel_header_names = self.settings["eg_kernel_headers"]
            for name in kernel_header_names:
                if name:  # Ignore things like empty strings
                    value = self.request.headers.get(name)
                    if value:
                        kernel_headers[name] = value
                    else:
                        missing_headers.append(name)

            if len(missing_headers):
                self.log.warning(
                    "The following headers specified in 'kernel-headers' were not found: {}".format(
                        missing_headers
                    )
                )

            # No way to override the call to start_kernel on the kernel manager
            # so do a temporary partial (ugh)
            orig_start = self.kernel_manager.start_kernel
            self.kernel_manager.start_kernel = partial(
                self.kernel_manager.start_kernel,
                env=env,
                kernel_headers=kernel_headers,
                tenant_id=tenant_id,
            )
            try:
                await super().post()
            finally:
                self.kernel_manager.start_kernel = orig_start
        else:
            await super().post()

    async def get(self):
        """Overrides the super class method to honor the kernel listing
        configuration setting.

        Allows the request to reach the super class if listing is enabled.

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if kernel listing is disabled
        """

        tenant_id_filter = self.request.query_arguments.get("tenant_id") or UNIVERSAL_TENANT_ID
        if isinstance(tenant_id_filter, list):
            tenant_id_filter = tenant_id_filter[0].decode("utf-8")
        if not self.settings.get("eg_list_kernels") and tenant_id_filter == UNIVERSAL_TENANT_ID:
            raise tornado.web.HTTPError(403, "Forbidden")
        else:
            km = self.kernel_manager
            kernels = await ensure_async(km.list_kernels(tenant_id=tenant_id_filter))
            self.finish(json.dumps(kernels, default=date_default))

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()


class KernelHandler(
    TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, jupyter_server_handlers.KernelHandler
):
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
