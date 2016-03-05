# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Class for building a Swagger spec from a notebook-defined API."""

import os
from ..cell.parser import APICellParser


class SwaggerSpecBuilder(object):
    """Builds a Swagger specification.

    Parameters
    ----------
    kernel_spec : str
        Name of the kernel language

    Attributes
    ----------
    cell_parser : services.cell.parser.APICellParser
        Finds cell annotations to add to the spec
    value : dict
        Python object representation of the Swagger spec
    """
    def __init__(self, kernel_spec):
        self.cell_parser = APICellParser(kernel_spec)
        self.value = { 'swagger' : '2.0', 'paths' : {}, 'info' : {'version' : '0.0.0', 'title' : 'Default Title'} }

    def add_cell(self, cell_source):
        """Parses a notebook cell for API annotations.

        If found, adds the HTTP verb and endpoint to the Swagger spec.

        Parameters
        ----------
        cell_source : str
            Source code from a notebook
        """
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

    def set_title(self, path):
        """Stores the root of a notebook filename as the API title.

        Parameters
        ----------
        path : url
            Path to the notebook file defining the API
        """
        basename = os.path.basename(path)
        self.value['info']['title'] = basename.split('.')[0] if basename.find('.') > 0 else basename

    def build(self):
        """Gets the specification.

        Returns
        -------
        dict
            Python object representation of the Swagger spec
        """
        return self.value
