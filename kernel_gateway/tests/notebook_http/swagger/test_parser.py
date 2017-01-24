# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for notebook cell parsing."""

import unittest
import sys
from kernel_gateway.notebook_http.swagger.parser import SwaggerCellParser


class TestSwaggerAPICellParser(unittest.TestCase):
    """Unit tests the SwaggerCellParser class."""
    def test_basic_swagger_parse(self):
        """Parser should correctly identify Swagger cells."""
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=[{"source":'```\n{"swagger":"2.0", "paths": {"": {"post": {"operationId": "foo", "parameters": [{"name": "foo"}]}}}}\n```\n'}])
        self.assertTrue('swagger' in parser.swagger, 'Swagger doc was not detected')

    def test_basic_is_api_cell(self):
        """Parser should correctly identify operation cells."""
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=[{"source":'```\n{"swagger":"2.0", "paths": {"": {"post": {"operationId": "foo", "parameters": [{"name": "foo"}]}}}}\n```\n'}])
        self.assertTrue(parser.is_api_cell('#operationId:foo'), 'API cell was not detected with ' + str(parser.kernelspec_operation_indicator))
        self.assertTrue(parser.is_api_cell('# operationId:foo'), 'API cell was not detected with ' + str(parser.kernelspec_operation_indicator))
        self.assertTrue(parser.is_api_cell('#operationId: foo'), 'API cell was not detected with ' + str(parser.kernelspec_operation_indicator))
        self.assertFalse(parser.is_api_cell('no'), 'API cell was detected')
        self.assertFalse(parser.is_api_cell('# another comment'), 'API cell was detected')

    def test_basic_is_api_response_cell(self):
        """Parser should correctly identify ResponseInfo cells."""
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=[{"source":'```\n{"swagger":"2.0", "paths": {"": {"post": {"operationId": "foo", "parameters": [{"name": "foo"}]}}}}\n```\n'}])
        self.assertTrue(parser.is_api_response_cell('#ResponseInfo operationId:foo'), 'Response cell was not detected with ' + str(parser.kernelspec_operation_response_indicator))
        self.assertTrue(parser.is_api_response_cell('# ResponseInfo operationId:foo'), 'Response cell was not detected with ' + str(parser.kernelspec_operation_response_indicator))
        self.assertTrue(parser.is_api_response_cell('# ResponseInfo  operationId: foo'), 'Response cell was not detected with ' + str(parser.kernelspec_operation_response_indicator))
        self.assertTrue(parser.is_api_response_cell('#ResponseInfo operationId: foo'), 'Response cell was not detected with ' + str(parser.kernelspec_operation_response_indicator))
        self.assertFalse(parser.is_api_response_cell('# operationId: foo'), 'API cell was detected as a ResponseInfo cell ' + str(parser.kernelspec_operation_response_indicator))
        self.assertFalse(parser.is_api_response_cell('no'), 'API cell was detected')

    def test_endpoint_sort_default_strategy(self):
        """Parser should sort duplicate endpoint paths."""
        source_cells = [
            {"source":'\n```\n{"swagger":"2.0","paths":{"":{"post":{"operationId":"postRoot","parameters":[{"name":"foo"}]}},"/hello":{"post":{"operationId":"postHello","parameters":[{"name":"foo"}]},"get":{"operationId":"getHello","parameters":[{"name":"foo"}]}},"/hello/world":{"put":{"operationId":"putWorld"}}}}\n```\n'},
            {"source":'# operationId:putWorld'},
            {"source":'# operationId:getHello'},
            {"source":'# operationId:postHello'},
            {"source":'# operationId:postRoot'},
        ]
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells = source_cells)
        endpoints = parser.endpoints(cell['source'] for cell in source_cells)

        expected_values = ['/hello/world', '/hello/:foo', '/:foo']
        try:
            for index in range(0, len(expected_values)):
                endpoint, _ = endpoints[index]
                self.assertEqual(expected_values[index], endpoint, 'Endpoint was not found in expected order')
        except IndexError:
            self.fail(endpoints)

    def test_endpoint_sort_custom_strategy(self):
        """Parser should sort duplicate endpoint paths using a custom sort
        strategy.
        """
        source_cells = [
            {"source":'```\n{"swagger": "2.0", "paths": {"/1": {"post": {"operationId": "post1"}},"/+": {"post": {"operationId": "postPlus"}},"/a": {"get": {"operationId": "getA"}}}}\n```\n'},
            {"source":'# operationId: post1'},
            {"source":'# operationId: postPlus'},
            {"source":'# operationId: getA'},
        ]

        def custom_sort_fun(endpoint):
            if endpoint.find('1') >= 0:
                return 0
            elif endpoint.find('a') >= 0:
                return 1
            else:
                return 2

        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=source_cells)
        endpoints = parser.endpoints((cell['source'] for cell in source_cells), custom_sort_fun)
        print(str(endpoints))

        expected_values = ['/+', '/a', '/1']
        for index in range(0, len(expected_values)):
            endpoint, _ = endpoints[index]
            self.assertEqual(expected_values[index], endpoint, 'Endpoint was not found in expected order')

    def test_get_cell_endpoint_and_verb(self):
        """Parser should extract API endpoint and verb from cell annotations."""
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=[{'source':'```\n{"swagger":"2.0", "paths": {"/foo": {"get": {"operationId": "getFoo"}}, "/bar/quo": {"post": {"operationId": "post_bar_Quo"}}}}\n```\n'}])
        endpoint, verb = parser.get_cell_endpoint_and_verb('# operationId: getFoo')
        self.assertEqual(endpoint, '/foo', 'Endpoint was not extracted correctly')
        self.assertEqual(verb.lower(), 'get', 'Endpoint was not extracted correctly')
        endpoint, verb = parser.get_cell_endpoint_and_verb('# operationId: post_bar_Quo')
        self.assertEqual(endpoint, '/bar/quo', 'Endpoint was not extracted correctly')
        self.assertEqual(verb.lower(), 'post', 'Endpoint was not extracted correctly')

        endpoint, verb = parser.get_cell_endpoint_and_verb('some regular code')
        self.assertEqual(endpoint, None, 'Endpoint was not extracted correctly (something was actually returned)')
        self.assertEqual(verb, None, 'Endpoint was not extracted correctly (something was actually returned)')

    def test_endpoint_concatenation(self):
        """Parser should concatenate multiple cells with the same verb+path."""
        cells = [
            {"source":'```\n{"swagger":"2.0", "paths": {"/foo": {"put": {"operationId":"putFoo","parameters": [{"name": "bar"}]},"post":{"operationId":"postFooBody"},"get": {"operationId":"getFoo","parameters": [{"name": "bar"}]}}}}\n```\n'},
            {"source":'# operationId: postFooBody '},
            {"source":'# unrelated comment '},
            {"source":'# operationId: putFoo'},
            {"source":'# operationId: puttFoo'},
            {"source":'# operationId: getFoo'},
            {"source":'# operationId: putFoo'}
        ]
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=cells)
        endpoints = parser.endpoints(cell['source'] for cell in cells)
        self.assertEqual(len(endpoints), 2, endpoints)
        # for ease of testing
        endpoints = dict(endpoints)
        self.assertEqual(len(endpoints['/foo']), 1)
        self.assertEqual(len(endpoints['/foo/:bar']), 2)
        self.assertEqual(endpoints['/foo']['post'], '# operationId: postFooBody \n')
        self.assertEqual(endpoints['/foo/:bar']['get'], '# operationId: getFoo\n')
        self.assertEqual(endpoints['/foo/:bar']['put'], '# operationId: putFoo\n# operationId: putFoo\n')

    def test_endpoint_response_concatenation(self):
        """Parser should concatenate multiple response cells with the same
        verb+path.
        """
        source_cells = [
            {"source":'```\n{"swagger":"2.0", "paths": {"/foo": {"put": {"operationId":"putbar","parameters": [{"name": "bar"}]},"post":{"operationId":"postbar"},"get": {"operationId":"get","parameters": [{"name": "bar"}]}}}}\n```\n'},
            {"source":'# ResponseInfo operationId: get'},
            {"source":'# ResponseInfo operationId: postbar '},
            {"source":'# ResponseInfo operationId: putbar'},
            {"source":'# ResponseInfo operationId: puttbar'},
            {"source":'ignored'},
            {"source":'# ResponseInfo operationId: putbar '}
        ]
        parser = SwaggerCellParser(comment_prefix='#', notebook_cells=source_cells)
        endpoints = parser.endpoint_responses(cell['source'] for cell in source_cells)
        self.assertEqual(len(endpoints), 2)
        # for ease of testing
        endpoints = dict(endpoints)
        self.assertEqual(len(endpoints['/foo']), 1)
        self.assertEqual(len(endpoints['/foo/:bar']), 2)
        self.assertEqual(endpoints['/foo']['post'], '# ResponseInfo operationId: postbar \n')
        self.assertEqual(endpoints['/foo/:bar']['put'], '# ResponseInfo operationId: putbar\n# ResponseInfo operationId: putbar \n')
        self.assertEqual(endpoints['/foo/:bar']['get'], '# ResponseInfo operationId: get\n')

    def test_undeclared_operations(self):
        if sys.version_info[:2] >= (3,4):
            """Parser should warn about operations that aren't documented in the
            swagger cell
            """
            source_cells = [
                {"source":'```\n{"swagger":"2.0", "paths": {"/foo": {"put": {"operationId":"putbar","parameters": [{"name": "bar"}]},"post":{"operationId":"postbar"},"get": {"operationId":"get","parameters": [{"name": "bar"}]}}}}\n```\n'},
                {"source":'# operationId: get'},
                {"source":'# operationId: postbar '},
                {"source":'# operationId: putbar'},
                {"source":'# operationId: extraOperation'},
            ]
            with self.assertLogs(level='WARNING') as warnings:
                SwaggerCellParser(comment_prefix='#', notebook_cells=source_cells)
                for output in warnings.output:
                    self.assertRegex(output, 'extraOperation')

    def test_undeclared_operations_reversed(self):
        if sys.version_info[:2] >= (3,4):
            """Parser should warn about operations that aren't documented in the
            swagger cell
            """
            source_cells = [
                {"source":'# operationId: get'},
                {"source":'# operationId: postbar '},
                {"source":'# operationId: putbar'},
                {"source":'# operationId: extraOperation'},
                {"source":'```\n{"swagger":"2.0", "paths": {"/foo": {"put": {"operationId":"putbar","parameters": [{"name": "bar"}]},"post":{"operationId":"postbar"},"get": {"operationId":"get","parameters": [{"name": "bar"}]}}}}\n```\n'},
            ]
            with self.assertLogs(level='WARNING') as warnings:
                SwaggerCellParser(comment_prefix='#', notebook_cells=source_cells)
                for output in warnings.output:
                    self.assertRegex(output, 'extraOperation')

    def test_unreferenced_operations(self):
        if sys.version_info[:2] >= (3,4):
            """Parser should warn about documented operations that aren't referenced
            in a cell
            """
            source_cells = [
                {"source": '```\n{"swagger":"2.0", "paths": {"/foo": {"put": {"operationId":"putbar","parameters": [{"name": "bar"}]},"post":{"operationId":"postbar"},"get": {"operationId":"get","parameters": [{"name": "bar"}]}}}}\n```\n'},
                {"source": '# operationId: get'},
                {"source": '# operationId: putbar'},
                {"source": '# operationId: putbar '}
            ]
            with self.assertLogs(level='WARNING') as warnings:
                SwaggerCellParser(comment_prefix='#', notebook_cells=source_cells)
                for output in warnings.output:
                    self.assertRegex(output, 'postbar')
