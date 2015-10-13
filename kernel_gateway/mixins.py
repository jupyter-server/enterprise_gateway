# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

class CORSMixin(object):
    '''
    Adds CORS headers to tornado.web.RequestHandlers.
    '''
    SETTINGS_TO_HEADERS = {
        'kg_allow_credentials': 'Access-Control-Allow-Credentials',
        'kg_allow_headers': 'Access-Control-Allow-Headers',
        'kg_allow_methods': 'Access-Control-Allow-Methods',
        'kg_allow_origin': 'Access-Control-Allow-Origin',
        'kg_expose_headers' : 'Access-Control-Expose-Headers',
        'kg_max_age': 'Access-Control-Max-Age'
    }
    def set_default_headers(self):
        '''
        Sets the CORS headers as the default for all responses. Disable CSP
        for the API.
        '''
        super(CORSMixin, self).set_default_headers()

        # Add CORS headers after default if they have a non-blank value
        for settings_name, header_name in self.SETTINGS_TO_HEADERS.items():
            header_value = self.settings.get(settings_name)
            if header_value:
                self.set_header(header_name, header_value)

        # Don't set CSP: we're not serving frontend media types only JSON
        self.clear_header('Content-Security-Policy')

class TokenAuthorizationMixin(object):
    '''
    Adds token authentication to tornado.web.RequestHandlers and 
    tornado.websocket.WebsocketHandlers.
    '''
    def prepare(self):
        '''
        If kg_auth_token is present in the application settings,
        raises 401 if the request Authorization header does not contain
        the value "token <kg_auth_token>".
        '''
        server_token = self.settings.get('kg_auth_token')
        if server_token:
            client_token = self.request.headers.get('Authorization')
            if client_token != 'token %s' % server_token:
                return self.send_error(401)
        return super(TokenAuthorizationMixin, self).prepare()