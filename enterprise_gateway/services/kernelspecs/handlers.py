# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel specs."""
import glob
import json
import notebook.services.kernelspecs.handlers as notebook_handlers
import notebook.kernelspecs.handlers as notebook_kernelspecs_resources_handlers
import asyncio
import concurrent.futures

import inspect
import os
import logging
import traceback
from pygments.lexer import default
from tornado import web, gen
from ipython_genutils import py3compat
from urllib.parse import unquote
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from ...base.handlers import APIHandler

pjoin = os.path.join


def url_unescape(path):
    """Unescape special characters in a URL path
    Turns '/foo%20bar/' into '/foo bar/'
    """
    return u'/'.join ([
        py3compat.str_to_unicode (unquote (p), encoding='utf8')
        for p in py3compat.unicode_to_str (path, encoding='utf8').split ('/')
    ])


def maybe_future(obj):
    """Like tornado's deprecated gen.maybe_future
    but more compatible with asyncio for recent versions
    of tornado
    """
    if inspect.isawaitable (obj):
        return asyncio.ensure_future (obj)
    elif isinstance (obj, concurrent.futures.Future):
        return asyncio.wrap_future (obj)
    else:
        # not awaitable, wrap scalar in future
        f = asyncio.Future ()
        f.set_result (obj)
        return f


def url_path_join(*pieces):
    """Join components of url into a relative url
    Use to prevent double slash when joining subpath. This will leave the
    initial and final / in place
    """
    initial = pieces[0].startswith ('/')
    final = pieces[-1].endswith ('/')
    stripped = [s.strip ('/') for s in pieces]
    result = '/'.join (s for s in stripped if s)
    if initial: result = '/' + result
    if final: result = result + '/'
    if result == '//': result = '/'
    return result


def is_kernelspec_model(spec_dict):
    """Returns True if spec_dict is already in proper form.  This will occur when using a gateway."""
    return isinstance (spec_dict, dict) and 'name' in spec_dict and 'spec' in spec_dict and 'resources' in spec_dict


def kernelspec_model(handler, name, spec_dict, resource_dir):
    """Load a KernelSpec by name and return the REST API model"""
    d = {
        'name': name,
        'spec': spec_dict,
        'resources': {}
    }

    # Add resource files if they exist
    resource_dir = resource_dir
    for resource in ['kernel.js', 'kernel.css']:
        if os.path.exists (pjoin (resource_dir, resource)):
            d['resources'][resource] = url_path_join (
                handler.base_url,
                'kernelspecs',
                name,
                resource
            )
    for logo_file in glob.glob (pjoin (resource_dir, 'logo-*')):
        fname = os.path.basename (logo_file)
        no_ext, _ = os.path.splitext (fname)
        d['resources'][no_ext] = url_path_join (
            handler.base_url,
            'kernelspecs',
            name,
            fname
        )
    return d


# Extends the default handlers from the notebook package with token auth, CORS
# and JSON errors.
default_handlers = []


def exists(obj, chain):
    _key = chain.pop(0)
    if _key in obj:
        return exists(obj[_key], chain) if chain else obj[_key]

def apply_user_filter(kernelspec_model, kernel_user = None):
  if kernel_user:
    # Check unauthorized list
    if exists(kernelspec_model, ['spec', 'metadata', 'process_proxy', 'config', 'unauthorized_users']):
      # Check if kernel_user in kernelspec_model
      unauthorized_list = kernelspec_model['spec']['metadata']['process_proxy']['config']['unauthorized_users']
      if kernel_user in unauthorized_list:
        return None
    # Now we have check that unauthorized list doesnt exist
    if exists(kernelspec_model, ['spec', 'metadata', 'process_proxy', 'config', 'authorized_users']):
      authorized_list = kernelspec_model['spec']['metadata']['process_proxy']['config']['authorized_users']
      if authorized_list and kernel_user not in authorized_list:
        return None
  return kernelspec_model

class ModifyKernelSpecHandler (APIHandler):
    @web.authenticated
    @gen.coroutine
    def get(self, kernel_user = None):
        ksm = self.kernel_spec_manager
        km = self.kernel_manager
        model = {}
        model['default'] = km.default_kernel_name
        model['kernelspecs'] = specs = {}
        kspecs = yield maybe_future (ksm.get_all_specs ())
        if kernel_user:
            self.log.info("Searching kernels for user '%s' " %kernel_user)
        else:
            self.log.info("No user. All kernels given")

        for kernel_name, kernel_info in kspecs.items ():
            try:
                if is_kernelspec_model (kernel_info):
                    d = kernel_info
                else:
                    d = kernelspec_model(self, kernel_name, kernel_info['spec'], kernel_info['resource_dir'])

                d = apply_user_filter(d, kernel_user)
                if d is not None:
                    self.log.info("Find kernel '%s'", d['name'])
                    specs[kernel_name] = d

            except Exception:
                self.log.error("Failed to load kernel spec: '%s'", kernel_name)
                continue
        self.set_header("Content-Type", 'application/json')
        self.finish(json.dumps(model))


kernel_name_regex = r"(?P<kernel_name>[\w\.\-%]+)"
kernel_user_regex = r"(?P<kernel_user>[\w%]+)"

default_handlers_notebooks = [
            (r"/api/kernelspecs", ModifyKernelSpecHandler),
            (r"/api/kernelspecs/user/%s" % kernel_user_regex, ModifyKernelSpecHandler),
            (r"/api/kernelspecs/%s" % kernel_name_regex, notebook_handlers.KernelSpecHandler)
]

for path, cls in default_handlers_notebooks:
    bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
    default_handlers.append((path, type(cls.__name__, bases, {})))

for path, cls in notebook_kernelspecs_resources_handlers.default_handlers:
    # Everything should have CORS and token auth
    bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
    default_handlers.append ((path, type(cls.__name__, bases, {})))

