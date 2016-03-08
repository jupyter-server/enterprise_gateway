# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for handler mixins."""

import json
import unittest
from tornado import web
from kernel_gateway.mixins import JSONErrorsMixin

class TestableHandler(JSONErrorsMixin):
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
        self.mixin = TestableHandler()

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
