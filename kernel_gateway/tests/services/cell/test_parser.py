# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for notebook cell parsing."""

import unittest
import re
import sys
from kernel_gateway.services.cell.parser import APICellParser

class TestAPICellParser(unittest.TestCase):
    """Unit tests the APICellParser class."""
    def _test_parser_with_kernel_spec(self, kernel_spec, expected_comment):
        """Instantiates the parser using the given `kernel_spec` and asserts
        whether it created the correct regular expression for the kernel
        language comment syntax.

        Parameters
        ----------
        kernel_spec : str
            Kernel spec name
        expected_comment : str
            Comment token in the kernel spec language

        Raises
        ------
        AssertionError
            If the parser did not create the correct regex
        """
        parser = APICellParser(kernel_spec)
        self.assertEqual(
            parser.kernelspec_api_indicator,
            re.compile(parser.api_indicator.format(expected_comment)),
            'Exepected regular expression to start with {} for kernel spec {}'.format(
                expected_comment,
                kernel_spec
            )
        )

    def test_init(self):
        """Parser should pick the correct comment syntax."""
        self._test_parser_with_kernel_spec('some_unknown_kernel', '#')
        self._test_parser_with_kernel_spec('scala', '//')
        self._test_parser_with_kernel_spec('python2', '#')
        self._test_parser_with_kernel_spec('python3', '#')
        self._test_parser_with_kernel_spec('ir', '#')
        self._test_parser_with_kernel_spec('julia-0.3', '#')

    def test_is_api_cell(self):
        """Parser should correctly identify annotated API cells."""
        parser = APICellParser('some_unknown_kernel')
        self.assertTrue(parser.is_api_cell('# GET /yes'), 'API cell was not detected')
        self.assertFalse(parser.is_api_cell('no'), 'API cell was not detected')

    def test_endpoint_sort_default_strategy(self):
        """Parser should sort duplicate endpoint paths."""
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

    def test_endpoint_sort_custom_strategy(self):
        """Parser should sort duplicate endpoint paths using a custom sort
        strategy.
        """
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
        """Parser should extract API endpoint and verb from cell annotations."""
        parser = APICellParser('some_unknown_kernel')
        endpoint, verb = parser.get_cell_endpoint_and_verb('# GET /foo')
        self.assertEqual(endpoint, '/foo', 'Endpoint was not extracted correctly')
        self.assertEqual(verb, 'GET', 'Endpoint was not extracted correctly')
        endpoint, verb = parser.get_cell_endpoint_and_verb('# POST /bar/quo')
        self.assertEqual(endpoint, '/bar/quo', 'Endpoint was not extracted correctly')
        self.assertEqual(verb, 'POST', 'Endpoint was not extracted correctly')

        endpoint, verb = parser.get_cell_endpoint_and_verb('some regular code')
        self.assertEqual(endpoint, None, 'Endpoint was not extracted correctly')
        self.assertEqual(verb, None, 'Endpoint was not extracted correctly')

    def test_endpoint_concatenation(self):
        """Parser should concatenate multiple cells with the same verb+path."""
        source_cells = [
            '# POST /foo/:bar',
            '# POST /foo/:bar',
            '# POST /foo',
            'ignored',
            '# GET /foo/:bar'
        ]
        parser = APICellParser('some_unknown_kernel')
        endpoints = parser.endpoints(source_cells)
        self.assertEqual(len(endpoints), 2)
        # for ease of testing
        endpoints = dict(endpoints)
        self.assertEqual(len(endpoints['/foo']), 1)
        self.assertEqual(len(endpoints['/foo/:bar']), 2)
        self.assertEqual(endpoints['/foo']['POST'], '# POST /foo\n')
        self.assertEqual(endpoints['/foo/:bar']['POST'], '# POST /foo/:bar\n# POST /foo/:bar\n')
        self.assertEqual(endpoints['/foo/:bar']['GET'], '# GET /foo/:bar\n')

    def test_endpoint_response_concatenation(self):
        """Parser should concatenate multiple response cells with the same
        verb+path.
        """
        source_cells = [
            '# ResponseInfo POST /foo/:bar',
            '# ResponseInfo POST /foo/:bar',
            '# ResponseInfo POST /foo',
            'ignored',
            '# ResponseInfo GET /foo/:bar'
        ]
        parser = APICellParser('some_unknown_kernel')
        endpoints = parser.endpoint_responses(source_cells)
        self.assertEqual(len(endpoints), 2)
        # for ease of testing
        endpoints = dict(endpoints)
        self.assertEqual(len(endpoints['/foo']), 1)
        self.assertEqual(len(endpoints['/foo/:bar']), 2)
        self.assertEqual(endpoints['/foo']['POST'], '# ResponseInfo POST /foo\n')
        self.assertEqual(endpoints['/foo/:bar']['POST'], '# ResponseInfo POST /foo/:bar\n# ResponseInfo POST /foo/:bar\n')
        self.assertEqual(endpoints['/foo/:bar']['GET'], '# ResponseInfo GET /foo/:bar\n')
