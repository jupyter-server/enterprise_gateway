# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import tornado
import notebook.services.kernels.handlers as notebook_handlers
from ...mixins import TokenAuthorizationMixin, CORSMixin

class MainKernelHandler(TokenAuthorizationMixin, 
                        CORSMixin, 
                        notebook_handlers.MainKernelHandler):
    def post(self):
        '''
        Honors the max number of allowed kernels configuration setting. Raises
        402 (for lack of a better HTTP error code) if at the limit.
        '''
        max_kernels = self.settings['kg_max_kernels']
        if max_kernels is not None:
            km = self.settings['kernel_manager']
            kernels = km.list_kernels()
            if len(kernels) >= max_kernels:
                raise tornado.web.HTTPError(402, 'Resource Limit')

        super(MainKernelHandler, self).post()

    def get(self):
        '''
        Denies returning a list of running kernels unless explicitly
        enabled, instead returning a 404 error.
        '''
        if 'kg_list_kernels' not in self.settings or self.settings['kg_list_kernels'] != True:
            raise tornado.web.HTTPError(404, 'Not Found')
        else:
            super(MainKernelHandler, self).get()

    # preemptively insert our own default when one is not specified
    def get_json_body(self):
        model = super(MainKernelHandler, self).get_json_body()
        if 'kg_default_kernel_name' in self.settings and self.settings['kg_default_kernel_name'] is not '':
            if model is None:
                model = {
                    'name': self.settings['kg_default_kernel_name']
                }
            else:
                model.setdefault('name', self.settings['kg_default_kernel_name'])
        return model

default_handlers = []
for path, cls in notebook_handlers.default_handlers:
    if cls.__name__ in globals():
        # Use the same named class from here if it exists
        default_handlers.append((path, globals()[cls.__name__]))
    else:
        # Gen a new type with CORS and token auth
        if path.endswith('channels'):
            # Websocket handler shouldn't have CORS headers
            bases = (TokenAuthorizationMixin, cls)
        else:
            bases = (TokenAuthorizationMixin, CORSMixin, cls)
        default_handlers.append((path, type(cls.__name__, bases, {})))
