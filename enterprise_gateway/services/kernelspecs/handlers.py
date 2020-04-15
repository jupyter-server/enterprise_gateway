# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel specs."""
import glob
import json
import notebook.services.kernelspecs.handlers as notebook_handlers
import notebook.kernelspecs.handlers as notebook_kernelspecs_resources_handlers
from notebook.utils import maybe_future
from notebook.services.kernelspecs.handlers import is_kernelspec_model, kernelspec_model

from tornado import web
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from ...base.handlers import APIHandler

# Extends the default handlers from the notebook package with token auth, CORS
# and JSON errors.
default_handlers = []


def key_exists(obj, chain):
    _key = chain.pop(0)
    if _key in obj:
        return key_exists(obj[_key], chain) if chain else obj[_key]


def apply_user_filter(kernelspec_model, kernel_user=None):
    if kernel_user:
        # Check unauthorized list
        if key_exists(kernelspec_model, ['spec', 'metadata', 'process_proxy', 'config', 'unauthorized_users']):
            # Check if kernel_user in kernelspec_model
            unauthorized_list = kernelspec_model['spec']['metadata']['process_proxy']['config']['unauthorized_users']
            if kernel_user in unauthorized_list:
                return None
        # Check authorized list
        if key_exists(kernelspec_model, ['spec', 'metadata', 'process_proxy', 'config', 'authorized_users']):
            authorized_list = kernelspec_model['spec']['metadata']['process_proxy']['config']['authorized_users']
            if authorized_list and kernel_user not in authorized_list:
                return None
    return kernelspec_model


class UserKernelSpecHandler(APIHandler):
    @web.authenticated
    async def get(self, kernel_user=None):
        ksm = self.kernel_spec_manager
        km = self.kernel_manager
        model = {}
        model['default'] = km.default_kernel_name
        model['kernelspecs'] = specs = {}
        kspecs = await maybe_future(ksm.get_all_specs())
        if kernel_user:
            self.log.debug("Searching kernels for user '%s' " % kernel_user)
        else:
            self.log.debug("No user. All kernels given")

        list_kernels_found = []
        for kernel_name, kernel_info in kspecs.items():
            try:
                if is_kernelspec_model(kernel_info):
                    d = kernel_info
                else:
                    d = kernelspec_model(self, kernel_name, kernel_info['spec'], kernel_info['resource_dir'])
                d = apply_user_filter(d, kernel_user)
                if d is not None:
                    specs[kernel_name] = d
                    list_kernels_found.append(d['name'])
            except Exception:
                self.log.error("Failed to load kernel spec: '%s'", kernel_name)
                continue
        self.set_header("Content-Type", 'application/json')
        self.finish(json.dumps(model))


kernel_name_regex = r"(?P<kernel_name>[\w\.\-%]+)"
kernel_user_regex = r"(?P<kernel_user>[\w%]+)"

default_handlers_notebooks = [
    (r"/api/kernelspecs", UserKernelSpecHandler),
    (r"/api/kernelspecs/user/%s" % kernel_user_regex, UserKernelSpecHandler),
    (r"/api/kernelspecs/%s" % kernel_name_regex, notebook_handlers.KernelSpecHandler)
]

for path, cls in default_handlers_notebooks:
    bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
    default_handlers.append((path, type(cls.__name__, bases, {})))

for path, cls in notebook_kernelspecs_resources_handlers.default_handlers:
    # Everything should have CORS and token auth
    bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
    default_handlers.append((path, type(cls.__name__, bases, {})))
