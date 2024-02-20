"""Tornado handlers for kernel specs."""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
from typing import Dict, List, Optional

from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.services.kernelspecs.handlers import is_kernelspec_model, kernelspec_model
from jupyter_server.utils import ensure_async, url_unescape
from tornado import web
from traitlets import Set

from ...base.handlers import APIHandler
from ...mixins import CORSMixin, JSONErrorsMixin, TokenAuthorizationMixin
from .kernelspec_cache import KernelSpecCache


def apply_user_filter(
    kernelspec_model: Dict[str, object],
    global_authorized_list: Set,
    global_unauthorized_list: Set,
    kernel_user: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    """
    If authorization lists are configured - either within the kernelspec or globally, ensure
    the user is authorized for the given kernelspec.
    """
    if kernel_user:
        # Check the unauthorized list of the kernelspec, then the globally-configured unauthorized list - the
        # semantics of which are a union of the two lists.
        try:
            # Check if kernel_user in kernelspec_model
            unauthorized_list = kernelspec_model["spec"]["metadata"]["process_proxy"]["config"][
                "unauthorized_users"
            ]
        except KeyError:
            pass
        else:
            if kernel_user in unauthorized_list:
                return None
        if kernel_user in global_unauthorized_list:
            return None

        # Check the authorized list of the kernelspec, then the globally-configured authorized list -
        # but only if the kernelspec list doesn't exist.  This is because the kernelspec set of authorized
        # users may be a subset of globally authorized users and is, essentially, used as a denial to those
        # not defined in the kernelspec's list.
        try:
            authorized_list = kernelspec_model["spec"]["metadata"]["process_proxy"]["config"][
                "authorized_users"
            ]
        except KeyError:
            if global_authorized_list and kernel_user not in global_authorized_list:
                return None
        else:
            if authorized_list and kernel_user not in authorized_list:
                return None

    return kernelspec_model


class MainKernelSpecHandler(TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, APIHandler):
    """The root kernel spec handler."""

    @property
    def kernel_spec_cache(self) -> KernelSpecCache:
        return self.settings["kernel_spec_cache"]

    @web.authenticated
    async def get(self) -> None:
        """Get the kernel spec models."""
        ksc = self.kernel_spec_cache
        km = self.kernel_manager
        model = {}
        model["default"] = km.default_kernel_name
        model["kernelspecs"] = specs = {}

        kernel_user_filter = self.request.query_arguments.get("user")
        kernel_user = None
        if kernel_user_filter:
            kernel_user = kernel_user_filter[0].decode("utf-8")
            if kernel_user:
                self.log.debug("Searching kernels for user '%s' " % kernel_user)

        kspecs = await ensure_async(ksc.get_all_specs())

        list_kernels_found = []
        for kernel_name, kernel_info in kspecs.items():
            try:
                if is_kernelspec_model(kernel_info):
                    d = kernel_info
                else:
                    d = kernelspec_model(
                        self, kernel_name, kernel_info["spec"], kernel_info["resource_dir"]
                    )
                d = apply_user_filter(
                    d,
                    self.settings["eg_authorized_users"],
                    self.settings["eg_unauthorized_users"],
                    kernel_user,
                )
                if d is not None:
                    specs[kernel_name] = d
                    list_kernels_found.append(d["name"])
                else:
                    self.log.debug(
                        f"User {kernel_user} is not authorized to use kernel spec {kernel_name}"
                    )
            except Exception:
                self.log.error("Failed to load kernel spec: '%s'", kernel_name)
                continue

        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(model))


class KernelSpecHandler(TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, APIHandler):
    """A handler for a specific kernel spec."""

    @property
    def kernel_spec_cache(self) -> KernelSpecCache:
        return self.settings["kernel_spec_cache"]

    @web.authenticated
    async def get(self, kernel_name: str) -> None:
        """Get a kernel spec by name."""
        ksc = self.kernel_spec_cache
        kernel_name = url_unescape(kernel_name)
        kernel_user_filter = self.request.query_arguments.get("user")
        kernel_user = None
        if kernel_user_filter:
            kernel_user = kernel_user_filter[0].decode("utf-8")
        try:
            spec = await ensure_async(ksc.get_kernel_spec(kernel_name))
        except KeyError:
            raise web.HTTPError(404, "Kernel spec %s not found" % kernel_name) from None
        if is_kernelspec_model(spec):
            model = spec
        else:
            model = kernelspec_model(self, kernel_name, spec.to_dict(), spec.resource_dir)
        d = apply_user_filter(
            model,
            self.settings["eg_authorized_users"],
            self.settings["eg_unauthorized_users"],
            kernel_user,
        )

        if d is None:
            raise web.HTTPError(
                403, f"User {kernel_user} is not authorized to use kernel spec {kernel_name}"
            )

        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(model))


class KernelSpecResourceHandler(
    TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, web.StaticFileHandler, JupyterHandler
):
    """A handler for kernel spec resources."""

    SUPPORTED_METHODS = ("GET", "HEAD")

    @property
    def kernel_spec_cache(self) -> KernelSpecCache:
        return self.settings["kernel_spec_cache"]

    def initialize(self) -> None:
        """Initialize the handler."""
        web.StaticFileHandler.initialize(self, path="")

    @web.authenticated
    async def get(self, kernel_name: str, path: str, include_body: bool = True) -> None:
        """Get a resource for a kernel."""
        ksc = self.kernel_spec_cache
        try:
            kernelspec = await ensure_async(ksc.get_kernel_spec(kernel_name))
            self.root = kernelspec.resource_dir
        except KeyError as e:
            raise web.HTTPError(404, "Kernel spec %s not found" % kernel_name) from e
        self.log.debug("Serving kernel resource from: %s", self.root)
        return await web.StaticFileHandler.get(self, path, include_body=include_body)

    @web.authenticated
    def head(self, kernel_name: str, path: str) -> None:
        """Get the head for a kernel resource."""
        return self.get(kernel_name, path, include_body=False)


kernel_name_regex: str = r"(?P<kernel_name>[\w\.\-%]+)"

# Extends the default handlers from the jupyter_server package with token auth, CORS
# and JSON errors.
default_handlers: List[tuple] = [
    (r"/api/kernelspecs", MainKernelSpecHandler),
    (r"/api/kernelspecs/%s" % kernel_name_regex, KernelSpecHandler),
    (r"/kernelspecs/%s/(?P<path>.*)" % kernel_name_regex, KernelSpecResourceHandler),
]
