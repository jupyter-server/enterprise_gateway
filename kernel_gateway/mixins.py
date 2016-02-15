# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
try:
    # py3
    from http.client import responses
except ImportError:
    from httplib import responses

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

class JSONErrorsMixin(object):
    '''
    Outputs all errors as JSON in the same format as the
    notebook.base.handlers.json_errors decorator. Avoids having to (re-)decorate
    everything that the kernel gateway overrides. Also avoids rendering errors
    as a human readable HTML pages in cases where the decorator is not used
    in the notebook code base.
    '''
    def write_error(self, status_code, **kwargs):
        '''
        Overrides the HTML renderer in the notebook server to force all errors
        to JSON format.
        '''
        exc_info = kwargs.get('exc_info')
        message = ''
        reason = responses.get(status_code, 'Unknown HTTP Error')
        if exc_info:
            exception = exc_info[1]
            # Get the custom message, if defined
            try:
                message = exception.log_message % exception.args
            except Exception:
                pass

            # Construct the custom reason, if defined
            custom_reason = getattr(exception, 'reason', '')
            if custom_reason:
                reason = custom_reason

        self.set_header('Content-Type', 'application/json')
        self.set_status(status_code)
        reply = dict(reason=reason, message=message)
        self.finish(json.dumps(reply))
