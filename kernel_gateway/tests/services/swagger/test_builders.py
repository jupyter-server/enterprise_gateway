# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from kernel_gateway.services.swagger.builders import *
import unittest
class TestSwaggerBuilders(unittest.TestCase):
    def test_add_title_adds_title_to_spec(self):
        '''When a title is set on the builder, it should be reflected in the result'''
        expected = 'Some New Title'
        builder = SwaggerSpecBuilder('some_spec')
        builder.set_title(expected)
        result = builder.build()
        self.assertEqual(result['info']['title'] ,expected,'Title was not set to new value')

    def test_add_cell_adds_api_cell_to_spec(self):
        '''When an api cell is added to the builder, it should be reflected in the result'''
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
        '''When a non-api cell is added to the builder, it should not be reflected in the result'''
        builder = SwaggerSpecBuilder('some_spec')
        builder.add_cell('regular code cell')
        result = builder.build()
        self.assertEqual(len(result['paths']) , 0,'Title was not set to new value')
