# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import notebook.services.kernels.handlers as notebook_handlers

class TokenAuthorizationMixin(object):
    '''
    Adds token authentication to tornado.web.RequestHandlers.
    '''
    def prepare(self):
        '''
        If kg_auth_token is present in the application settings,
        raises 401 if the request Authorization header does not contain
        the value "Token <kg_auth_token>".
        '''
        server_token = self.settings.get('kg_auth_token')
        if server_token:
            client_token = self.request.headers.get('Authorization')
            if client_token != 'Token %s' % server_token:
                return self.send_error(401)
        return super(TokenAuthorizationMixin, self).prepare()

# Build a new type with the token auth mixin for each default kernel handler
# in the notebook project
default_handlers = [(path, type(cls.__name__, (TokenAuthorizationMixin, cls), {})) 
                    for path, cls in notebook_handlers.default_handlers]
