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
