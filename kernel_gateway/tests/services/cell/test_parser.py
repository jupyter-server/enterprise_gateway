# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from kernel_gateway.services.cell.parser import *
import unittest
import re
class TestAPICellParserUtils(unittest.TestCase):
    def _test_parser_with_kernel_spec(self, kernel_spec, expected_comment):
        parser = APICellParser(kernel_spec)
        self.assertEqual(
            parser.kernelspec_api_indicator,
            re.compile(parser.api_indicator.format(expected_comment)),
            'Exepected regular expression to start with {} for kernel spec {}'.format(
                expected_comment,
                kernel_spec
            )
        )

    def test_init_uses_correct_default_comment(self):
        '''Tests if the parser correctly sets the comment regex for unknown kernels'''
        self._test_parser_with_kernel_spec('some_unknown_kernel', '#')

    def test_init_uses_correct_comment_for_spark_kernel(self):
        '''Tests if the parser correctly sets the comment regex for spark kernel'''
        self._test_parser_with_kernel_spec('scala', '//')

    def test_init_uses_correct_comment_for_python2_kernel(self):
        '''Tests if the parser correctly sets the comment regex for python2'''
        self._test_parser_with_kernel_spec('python2', '#')

    def test_init_uses_correct_comment_for_python3_kernel(self):
        '''Tests if the parser correctly sets the comment regex for python3'''
        self._test_parser_with_kernel_spec('python3', '#')

    def test_init_uses_correct_comment_for_ir_kernel(self):
        '''Tests if the parser correctly sets the comment regex for r'''
        self._test_parser_with_kernel_spec('ir', '#')

    def test_init_uses_correct_comment_for_julia_kernel(self):
        '''Tests if the parser correctly sets the comment regex for julia'''
        self._test_parser_with_kernel_spec('julia-0.3', '#')

    def test_is_api_cell_is_true_for_api_cells(self):
        '''Tests if the parser correctly identifies api cells'''
        parser = APICellParser('some_unknown_kernel')
        self.assertTrue(parser.is_api_cell('# GET /yes'), 'API cell was not detected')

    def test_is_api_cell_is_false_for_api_cells(self):
        '''Tests if the parser correctly identifies non-api cells'''
        parser = APICellParser('some_unknown_kernel')
        self.assertFalse(parser.is_api_cell('no'), 'API cell was not detected')

    def test_endpoints_are_sorted_default_strategy(self):
        '''Tests if the parser correctly creates a list of endpoint, source tuples using the default sort strategy'''
        source_cells = [
            '# POST /:foo',
            '# POST /hello/:foo',
            '# GET /hello/:foo',
            '# PUT /hello/world'
        ]
        parser = APICellParser('some_unknown_kernel')
        endpoints = parser.endpoints(source_cells)
        expected_values = ['/hello/world', '/hello/:foo', '/:foo']

        for index in range(0, len(expected_values)):
            endpoint, _ = endpoints[index]
            self.assertEqual(expected_values[index], endpoint, 'Endpoint was not found in expected order')

    def test_endpoints_are_sorted_default_strategy(self):
        '''Tests if the parser correctly creates a list of endpoint, source tuples using a custom sort strategy'''
        source_cells = [
            '# POST /1',
            '# POST /+',
            '# GET /a'
        ]

        def custom_sort_fun(endpoint):
            index = sys.maxsize
            if endpoint.find('1') >= 0:
                return 0
            elif endpoint.find('a') >= 0:
                return 1
            else:
                return 2

        parser = APICellParser('some_unknown_kernel')
        endpoints = parser.endpoints(source_cells, custom_sort_fun)
        expected_values = ['/+', '/a', '/1']

        for index in range(0, len(expected_values)):
            endpoint, _ = endpoints[index]
            self.assertEqual(expected_values[index], endpoint, 'Endpoint was not found in expected order')

    def test_get_cell_endpoint_and_verb(self):
        '''Tests the ability to extract API endpoint and verb from a cell'''
        parser = APICellParser('some_unknown_kernel')
        endpoint, verb = parser.get_cell_endpoint_and_verb('# GET /foo')
        self.assertEqual(endpoint, '/foo', 'Endpoint was not extracted correctly')
        self.assertEqual(verb, 'GET', 'Endpoint was not extracted correctly')
        endpoint, verb = parser.get_cell_endpoint_and_verb('# POST /bar/quo')
        self.assertEqual(endpoint, '/bar/quo', 'Endpoint was not extracted correctly')
        self.assertEqual(verb, 'POST', 'Endpoint was not extracted correctly')

    def test_get_cell_endpoint_and_verb_with_non_api_cell(self):
        '''Tests the ability to extract API endpoint and verb from a cell when there is no API code'''
        parser = APICellParser('some_unknown_kernel')
        endpoint, verb = parser.get_cell_endpoint_and_verb('some regular code')
        self.assertEqual(endpoint, None, 'Endpoint was not extracted correctly')
        self.assertEqual(verb, None, 'Endpoint was not extracted correctly')
