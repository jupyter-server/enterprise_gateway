from kernel_gateway.services.notebooks.request_utils import *
import unittest

class TestRequestUtils(unittest.TestCase):
    def test_parse_body_text(self):
        result = parse_body(b'"test value"')
        self.assertEqual(result, "test value", 'Did not properly parse text body.')

    def test_parse_body_json(self):
        result = parse_body(b'{ "foo" : "bar" }')
        self.assertEqual(result, { 'foo' : 'bar' }, 'Did not properly parse json body.')

    def test_parse_body_empty(self):
        result = parse_body(b'')
        self.assertEqual(result, '', 'Did not properly handle body = empty string.')

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
