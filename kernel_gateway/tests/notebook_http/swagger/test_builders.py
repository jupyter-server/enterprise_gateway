# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for swagger spec generation."""

import json
import unittest
from nose.tools import assert_not_equal
from kernel_gateway.notebook_http.swagger.builders import SwaggerSpecBuilder
from kernel_gateway.notebook_http.cell.parser import APICellParser
from kernel_gateway.notebook_http.swagger.parser import SwaggerCellParser

class TestSwaggerBuilders(unittest.TestCase):
    """Unit tests the swagger spec builder."""
    def test_add_title_adds_title_to_spec(self):
        """Builder should store an API title."""
        expected = 'Some New Title'
        builder = SwaggerSpecBuilder(APICellParser(comment_prefix='#'))
        builder.set_default_title(expected)
        result = builder.build()
        self.assertEqual(result['info']['title'] ,expected,'Title was not set to new value')

    def test_add_cell_adds_api_cell_to_spec(self):
        """Builder should store an API cell annotation."""
        expected = {
            'get' : {
                'responses' : {
                    200 : { 'description': 'Success'}
                }
            }
        }
        builder = SwaggerSpecBuilder(APICellParser(comment_prefix='#'))
        builder.add_cell('# GET /some/resource')
        result = builder.build()
        self.assertEqual(result['paths']['/some/resource'] ,expected,'Title was not set to new value')

    def test_all_swagger_preserved_in_spec(self):
        """Builder should store the swagger documented cell."""
        expected = '''
        {
            "swagger": "2.0",
            "info" : {"version" : "0.0.0", "title" : "Default Title"},
            "paths": {
                "/some/resource": {
                    "get": {
                        "summary": "Get some resource",
                        "description": "Get some kind of resource?",
                        "operationId": "getSomeResource",
                        "produces": [
                            "application/json"
                        ],
                        "responses": {
                            "200": {
                                "description": "a resource",
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {
                                            "type": "string"
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Error retrieving resources",
                                "schema": {
                                    "$ref": "#/definitions/error"
                                }
                            }
                        }
                    }
                }
            }
        }
        '''
        builder = SwaggerSpecBuilder(SwaggerCellParser(comment_prefix='#', notebook_cells = [{"source":expected}]))
        builder.add_cell(expected)
        result = builder.build()
        self.maxDiff = None
        self.assertEqual(result['paths']['/some/resource']['get']['description'], json.loads(expected)['paths']['/some/resource']['get']['description'], 'description was not preserved')
        self.assertTrue('info' in result, 'info was not preserved')
        self.assertTrue('title' in result['info'], 'title was not present')
        self.assertEqual(result['info']['title'], json.loads(expected)['info']['title'], 'title was not preserved')
        self.assertEqual(json.dumps(result['paths']['/some/resource'], sort_keys=True), json.dumps(json.loads(expected)['paths']['/some/resource'], sort_keys=True), 'operations were not as expected')

        new_title = 'new title. same contents.'
        builder.set_default_title(new_title)
        result = builder.build()
        assert_not_equal(result['info']['title'], new_title, 'title should not have been changed')

    def test_add_undocumented_cell_does_not_add_non_api_cell_to_spec(self):
        """Builder should store ignore non-API cells."""
        builder = SwaggerSpecBuilder(SwaggerCellParser(comment_prefix='#'))
        builder.add_cell('regular code cell')
        builder.add_cell('# regular commented cell')
        result = builder.build()
        self.assertEqual('paths' in result , 0, 'unexpected paths were found')
