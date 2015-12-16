# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from kernel_gateway.services.notebooks.request_utils import *
import unittest

class MockRequest(dict):
    def __init__(self, *args, **kwargs):
        super(MockRequest, self).__init__(*args, **kwargs)
        self.__dict__ = self


class TestRequestUtils(unittest.TestCase):
    def test_parse_body_text(self):
        request = MockRequest()
        request.body = b'test value'
        request.headers = {
            'Content-Type' : 'text/plain'
        }
        result = parse_body(request)
        self.assertEqual(result, "test value", 'Did not properly parse text body.')

    def test_parse_body_json(self):
        request = MockRequest()
        request.body = b'{ "foo" : "bar" }'
        request.headers = {
            'Content-Type' : 'application/json'
        }
        result = parse_body(request)
        self.assertEqual(result, { 'foo' : 'bar' }, 'Did not properly parse json body.')

    def test_parse_body_bad_json(self):
        request = MockRequest()
        request.body = b'{ "foo" "bar" }'
        request.headers = {
            'Content-Type' : 'application/json'
        }
        result = parse_body(request)
        self.assertEqual(result, '{ "foo" "bar" }', 'Did not properly parse json body.')


    def test_parse_body_multipart_form(self):
        request = MockRequest()
        request.body = None
        request.body_arguments = { 'foo' : [b'bar']}
        request.headers = {
            'Content-Type' : 'multipart/form-data'
        }
        result = parse_body(request)
        self.assertEqual(result, { 'foo' : ['bar']}, 'Did not properly parse json body.')

    def test_parse_body_url_encoded_form(self):
        request = MockRequest()
        request.body = None
        request.body_arguments = { 'foo' : [b'bar']}
        request.headers = {
            'Content-Type' : 'application/x-www-form-urlencoded'
        }
        result = parse_body(request)
        self.assertEqual(result, { 'foo' : ['bar']}, 'Did not properly parse json body.')

    def test_parse_body_empty(self):
        request = MockRequest()
        request.body = b''
        request.headers = {}
        result = parse_body(request)
        self.assertEqual(result, '', 'Did not properly handle body = empty string.')

    def test_parse_body_defaults_to_text_plain(self):
        request = MockRequest()
        request.body = b'{"foo" : "bar"}'
        request.headers = {}
        result = parse_body(request)
        self.assertEqual(result, '{"foo" : "bar"}', 'Did not properly handle body = empty string.')

    def test_parse_args(self):
        result = parse_args({'arga': [ b'1234', b'4566'], 'argb' : [b'hello']})
        self.assertEqual(
            result,
            {'arga': ['1234', '4566'], 'argb' : ['hello']},
            'Did not properly convert query parameters.'
        )

    def test_parameterize_path(self):
        result = parameterize_path('/foo/:bar')
        self.assertEqual(result, '/foo/(?P<bar>[^\/]+)')
        result = parameterize_path('/foo/:bar/baz/:quo')
        self.assertEqual(result, '/foo/(?P<bar>[^\/]+)/baz/(?P<quo>[^\/]+)')

    def test_whitespace_in_paths(self):
        result = parameterize_path('/foo/:bar ')
        self.assertEqual(result, '/foo/(?P<bar>[^\/]+)')
        result = parameterize_path('/foo/:bar/baz ')
        self.assertEqual(result, '/foo/(?P<bar>[^\/]+)/baz')
