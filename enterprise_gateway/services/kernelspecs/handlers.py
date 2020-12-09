# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel specs."""
import json

from notebook.base.handlers import IPythonHandler
from notebook.services.kernelspecs.handlers import is_kernelspec_model, kernelspec_model
from notebook.utils import maybe_future, url_unescape
from tornado import web
from ...base.handlers import APIHandler
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin


def key_exists(obj, chain):
    """
    Ensures every entry in the chain array exists as a key in nested dictionaries of obj,
    returning the value of the last key
    """
    _key = chain.pop(0)
    if _key in obj:
        return key_exists(obj[_key], chain) if chain else obj[_key]


def apply_user_filter(kernelspec_model, global_authorized_list, global_unauthorized_list, kernel_user=None):
    """
    If authorization lists are configured - either within the kernelspec or globally, ensure
    the user is authorized for the given kernelspec.
    """
    if kernel_user:
        # Check the unauthorized list of the kernelspec, then the globally-configured unauthorized list - the
        # semantics of which are a union of the two lists.
        if key_exists(kernelspec_model, ['spec', 'metadata', 'process_proxy', 'config', 'unauthorized_users']):
            # Check if kernel_user in kernelspec_model
            unauthorized_list = kernelspec_model['spec']['metadata']['process_proxy']['config']['unauthorized_users']
            if kernel_user in unauthorized_list:
                return None
        if global_unauthorized_list and kernel_user in global_unauthorized_list:
            return None

        # Check the authorized list of the kernelspec, then the globally-configured authorized list -
        # but only if the kernelspec list doesn't exist.  This is because the kernelspec set of authorized
        # users may be a subset of globally authorized users and is, essentially, used as a denial to those
        # not defined in the kernelspec's list.
        if key_exists(kernelspec_model, ['spec', 'metadata', 'process_proxy', 'config', 'authorized_users']):
            authorized_list = kernelspec_model['spec']['metadata']['process_proxy']['config']['authorized_users']
            if authorized_list and kernel_user not in authorized_list:
                return None
        elif global_authorized_list and kernel_user not in global_authorized_list:
            return None

    return kernelspec_model


class MainKernelSpecHandler(TokenAuthorizationMixin,
                            CORSMixin,
                            JSONErrorsMixin,
                            APIHandler):

    @property
    def kernel_spec_cache(self):
        return self.settings['kernel_spec_cache']

    @web.authenticated
    async def get(self):
        ksm = self.kernel_spec_cache
        km = self.kernel_manager
        model = {}
        model['default'] = km.default_kernel_name
        model['kernelspecs'] = specs = {}

        kernel_user_filter = self.request.query_arguments.get('user')
        kernel_user = None
        if kernel_user_filter:
            kernel_user = kernel_user_filter[0].decode("utf-8")
            if kernel_user:
                self.log.debug("Searching kernels for user '%s' " % kernel_user)

        kspecs = await maybe_future(ksm.get_all_specs())

        list_kernels_found = []
        for kernel_name, kernel_info in kspecs.items():
            try:
                if is_kernelspec_model(kernel_info):
                    d = kernel_info
                else:
                    d = kernelspec_model(self, kernel_name, kernel_info['spec'], kernel_info['resource_dir'])
                d = apply_user_filter(d, self.settings['eg_authorized_users'],
                                      self.settings['eg_unauthorized_users'], kernel_user)
                if d is not None:
                    specs[kernel_name] = d
                    list_kernels_found.append(d['name'])
                else:
                    self.log.debug('User %s is not authorized to use kernel spec %s' % (kernel_user, kernel_name))
            except Exception:
                self.log.error("Failed to load kernel spec: '%s'", kernel_name)
                continue

        self.set_header("Content-Type", 'application/json')
        self.finish(json.dumps(model))


class KernelSpecHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        APIHandler):

    @property
    def kernel_spec_cache(self):
        return self.settings['kernel_spec_cache']

    @web.authenticated
    async def get(self, kernel_name):
        ksm = self.kernel_spec_cache
        kernel_name = url_unescape(kernel_name)
        kernel_user_filter = self.request.query_arguments.get('user')
        kernel_user = None
        if kernel_user_filter:
            kernel_user = kernel_user_filter[0].decode("utf-8")
        try:
            spec = await maybe_future(ksm.get_kernel_spec(kernel_name))
        except KeyError:
            raise web.HTTPError(404, u'Kernel spec %s not found' % kernel_name)
        if is_kernelspec_model(spec):
            model = spec
        else:
            model = kernelspec_model(self, kernel_name, spec.to_dict(), spec.resource_dir)
        d = apply_user_filter(model, self.settings['eg_authorized_users'],
                              self.settings['eg_unauthorized_users'], kernel_user)

        if d is None:
            raise web.HTTPError(403, u'User %s is not authorized to use kernel spec %s'
                                % (kernel_user, kernel_name))

        self.set_header("Content-Type", 'application/json')
        self.finish(json.dumps(model))


class KernelSpecResourceHandler(TokenAuthorizationMixin,
                                CORSMixin,
                                JSONErrorsMixin,
                                web.StaticFileHandler,
                                IPythonHandler):
    SUPPORTED_METHODS = ('GET', 'HEAD')

    @property
    def kernel_spec_cache(self):
        return self.settings['kernel_spec_cache']

    def initialize(self):
        web.StaticFileHandler.initialize(self, path='')

    @web.authenticated
    async def get(self, kernel_name, path, include_body=True):
        ksm = self.kernel_spec_cache
        try:
            kernelspec = await maybe_future(ksm.get_kernel_spec(kernel_name))
            self.root = kernelspec.resource_dir
        except KeyError as e:
            raise web.HTTPError(404,
                                u'Kernel spec %s not found' % kernel_name) from e
        self.log.debug("Serving kernel resource from: %s", self.root)
        return await web.StaticFileHandler.get(self, path, include_body=include_body)

    @web.authenticated
    def head(self, kernel_name, path):
        return self.get(kernel_name, path, include_body=False)


kernel_name_regex = r"(?P<kernel_name>[\w\.\-%]+)"

# Extends the default handlers from the notebook package with token auth, CORS
# and JSON errors.
default_handlers = [
    (r"/api/kernelspecs", MainKernelSpecHandler),
    (r"/api/kernelspecs/%s" % kernel_name_regex, KernelSpecHandler),
    (r"/kernelspecs/%s/(?P<path>.*)" % kernel_name_regex, KernelSpecResourceHandler),
]
