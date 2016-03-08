# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for swagger spec generation."""

import unittest
from kernel_gateway.services.swagger.builders import SwaggerSpecBuilder

class TestSwaggerBuilders(unittest.TestCase):
    """Unit tests the swagger spec builder."""
    def test_add_title_adds_title_to_spec(self):
        """Builder should store an API title."""
        expected = 'Some New Title'
        builder = SwaggerSpecBuilder('some_spec')
        builder.set_title(expected)
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
        builder = SwaggerSpecBuilder('some_spec')
        builder.add_cell('# GET /some/resource')
        result = builder.build()
        self.assertEqual(result['paths']['/some/resource'] ,expected,'Title was not set to new value')

    def test_add_cell_does_not_add_non_api_cell_to_spec(self):
        """Builder should store ignore non- API cells."""
        builder = SwaggerSpecBuilder('some_spec')
        builder.add_cell('regular code cell')
        result = builder.build()
        self.assertEqual(len(result['paths']) , 0,'Title was not set to new value')
