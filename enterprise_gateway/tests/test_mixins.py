# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for handler mixins."""

import json
import unittest

try:
    from unittest.mock import Mock, MagicMock
except ImportError:
    # Python 2.7: use backport
    from mock import Mock, MagicMock

from tornado import web
from kernel_gateway.mixins import TokenAuthorizationMixin, JSONErrorsMixin

class SuperTokenAuthHandler(object):
    """Super class for the handler using TokenAuthorizationMixin."""
    is_prepared = False

    def prepare(self):
        # called by the mixin when authentication succeeds
        self.is_prepared = True

class TestableTokenAuthHandler(TokenAuthorizationMixin, SuperTokenAuthHandler):
    """Implementation that uses the TokenAuthorizationMixin for testing."""
    def __init__(self, token=''):
        self.settings = { 'kg_auth_token': token }
        self.arguments = {}
        self.response = None
        self.status_code = None

    def send_error(self, status_code):
        self.status_code = status_code

    def get_argument(self, name, default=''):
        return self.arguments.get(name, default)


class TestTokenAuthMixin(unittest.TestCase):
    """Unit tests the Token authorization mixin."""
    def setUp(self):
        """Creates a handler that uses the mixin."""
        self.mixin = TestableTokenAuthHandler('YouKnowMe')

    def test_no_token_required(self):
        """Status should be None."""
        self.mixin.settings['kg_auth_token'] = ''
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, True)
        self.assertEqual(self.mixin.status_code, None)

    def test_missing_token(self):
        """Status should be 'unauthorized'."""
        attrs = { 'headers' : {
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, False)
        self.assertEqual(self.mixin.status_code, 401)

    def test_valid_header_token(self):
        """Status should be None."""
        attrs = { 'headers' : {
            'Authorization' : 'token YouKnowMe'
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, True)
        self.assertEqual(self.mixin.status_code, None)

    def test_wrong_header_token(self):
        """Status should be 'unauthorized'."""
        attrs = { 'headers' : {
            'Authorization' : 'token NeverHeardOf'
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, False)
        self.assertEqual(self.mixin.status_code, 401)

    def test_valid_url_token(self):
        """Status should be None."""
        self.mixin.arguments['token'] = 'YouKnowMe'
        attrs = { 'headers' : {
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, True)
        self.assertEqual(self.mixin.status_code, None)

    def test_wrong_url_token(self):
        """Status should be 'unauthorized'."""
        self.mixin.arguments['token'] = 'NeverHeardOf'
        attrs = { 'headers' : {
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, False)
        self.assertEqual(self.mixin.status_code, 401)

    def test_differing_tokens_valid_url(self):
        """Status should be None, URL token takes precedence"""
        self.mixin.arguments['token'] = 'YouKnowMe'
        attrs = { 'headers' : {
            'Authorization' : 'token NeverHeardOf'
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, True)
        self.assertEqual(self.mixin.status_code, None)

    def test_differing_tokens_wrong_url(self):
        """Status should be 'unauthorized', URL token takes precedence"""
        attrs = { 'headers' : {
            'Authorization' : 'token YouKnowMe'
        } }
        self.mixin.request = Mock(**attrs)
        self.mixin.arguments['token'] = 'NeverHeardOf'
        self.mixin.prepare()
        self.assertEqual(self.mixin.is_prepared, False)
        self.assertEqual(self.mixin.status_code, 401)


class TestableJSONErrorsHandler(JSONErrorsMixin):
    """Implementation that uses the JSONErrorsMixin for testing."""
    def __init__(self):
        self.headers = {}
        self.response = None
        self.status_code = None

    def finish(self, response):
        self.response = response

    def set_status(self, status_code):
        self.status_code = status_code

    def set_header(self, name, value):
        self.headers[name] = value

class TestJSONErrorsMixin(unittest.TestCase):
    """Unit tests the JSON errors mixin."""
    def setUp(self):
        """Creates a handler that uses the mixin."""
        self.mixin = TestableJSONErrorsHandler()

    def test_status(self):
        """Status should be set on the response."""
        self.mixin.write_error(404)
        response = json.loads(self.mixin.response)
        self.assertEqual(self.mixin.status_code, 404)
        self.assertEqual(response['reason'], 'Not Found')
        self.assertEqual(response['message'], '')

    def test_custom_status(self):
        """Custom reason from exeception should be set in the response."""
        exc = web.HTTPError(500, reason='fake-reason')
        self.mixin.write_error(500, exc_info=[None, exc])

        response = json.loads(self.mixin.response)
        self.assertEqual(self.mixin.status_code, 500)
        self.assertEqual(response['reason'], 'fake-reason')
        self.assertEqual(response['message'], '')

    def test_log_message(self):
        """Custom message from exeception should be set in the response."""
        exc = web.HTTPError(410, log_message='fake-message')
        self.mixin.write_error(410, exc_info=[None, exc])

        response = json.loads(self.mixin.response)
        self.assertEqual(self.mixin.status_code, 410)
        self.assertEqual(response['reason'], 'Gone')
        self.assertEqual(response['message'], 'fake-message')
