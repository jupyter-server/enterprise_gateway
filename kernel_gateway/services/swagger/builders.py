# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

from ..cell.parser import APICellParser
from os import path

class SwaggerSpecBuilder(object):
    '''
    Builds a swagger specification by calling the various methods to add more
    components to the specification.
    '''
    def __init__(self, kernel_spec):
        self.cell_parser = APICellParser(kernel_spec)
        self.value = { 'swagger' : '2.0', 'paths' : {}, 'info' : {'version' : '0.0.0', 'title' : 'Default Title'} }

    def add_cell(self, cell_source):
        '''Parses the cell for API comments. If some are found then the HTTP verb
        and endpoint for the cell are added to the swagger specification.
        '''
        if self.cell_parser.is_api_cell(cell_source):
            path_name, verb = self.cell_parser.get_cell_endpoint_and_verb(cell_source)
            path_value = {
                'responses' : {
                    200 : { 'description': 'Success'}
                }
            }
            if not path_name in self.value['paths']:
                self.value['paths'][path_name] = {}
            self.value['paths'][path_name][verb.lower()] = path_value

    def set_title(self, title):
        '''Sets the name of the the API to be title'''
        basename = path.basename(title)
        self.value['info']['title'] = basename.split('.')[0] if basename.find('.') > 0 else basename

    def build(self):
        '''Returns the dict object representing the swagger specification.'''
        return self.value
