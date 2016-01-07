# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from kernel_gateway.services.notebooks.request_utils import *
import unittest, json

class MockRequest(dict):
    def __init__(self, *args, **kwargs):
        super(MockRequest, self).__init__(*args, **kwargs)
        self.__dict__ = self

class MockHeaders(object):
    def __init__(self, headers, **kwargs):
        self.headers = headers

    def get_all(self):
        return self.headers

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

    def test_headers_to_dict(self):
        result = headers_to_dict(MockHeaders([('Content-Type', 'application/json'), ('Set-Cookie', 'A=B'), ('Set-Cookie', 'C=D')]))
        self.assertEqual(result['Content-Type'], 'application/json','Single value for header was not assigned correctly')
        self.assertEqual(result['Set-Cookie'], ['A=B','C=D'],'Single value for header was not assigned correctly')

    def test_headers_to_dict_with_no_headers(self):
        result = headers_to_dict(MockHeaders([]))
        self.assertEqual(result, {},'Empty headers handled incorrectly and did not make empty dict')

        def test_format_request_code_not_escaped(self):
            '''Test formatting request code without escaped quotes'''
        test_request = ('{"body": "", "headers": {"Accept-Language": "en-US,en;q=0.8", '
                        '"If-None-Match": "9a28a9262f954494a8de7442c63d6d0715ce0998", '
                        '"Accept-Encoding": "gzip, deflate, sdch"}, "args": {}, "path": {}}')
        request_code = format_request(test_request)
        #Get the value of REQUEST = "{ to test for equality
        test_request_js_value = request_code[request_code.index("\"{"):]
        self.assertEqual(test_request, json.loads(test_request_js_value), "Request code without escaped quotes was not formatted correctly")

    def test_format_request_code_escaped(self):
        '''Test formatting request code where multiple escaped quotes exist'''
        test_request = ('{"body": "", "headers": {"Accept-Language": "en-US,en;q=0.8", '
                        '"If-None-Match": "\"\"9a28a9262f954494a8de7442c63d6d0715ce0998\"\"", '
                        '"Accept-Encoding": "gzip, deflate, sdch"}, "args": {}, "path": {}}')
        request_code = format_request(test_request)
        #Get the value of REQUEST = "{ to test for equality
        test_request_js_value = request_code[request_code.index("\"{"):]
        self.assertEqual(test_request, json.loads(test_request_js_value), "Escaped Request code was not formatted correctly")
