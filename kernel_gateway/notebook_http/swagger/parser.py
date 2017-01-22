# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Parser for notebook with a single markdown cell containing Swagger API definition."""

import json
import re
from kernel_gateway.notebook_http.cell.parser import first_path_param_index, APICellParser
from traitlets import default
from traitlets.config.configurable import LoggingConfigurable

def _swaggerlet_from_markdown(cell_source):
    """ Pulls apart the first block comment of a cell's source,
    then tries to parse it as a JSON object. If it contains a 'swagger'
    property, returns it.
    """
    lines = cell_source.splitlines()
    # pull out the first block comment
    if len(lines) > 2:
        for i in range(0, len(lines)):
            if lines[i].startswith("```"):
                lines = lines[i+1:]
                break
        for i in range(0, len(lines)):
            if lines[i].startswith("```"):
                lines = lines[:i]
                break
    # parse the comment as JSON and check for a "swagger" property
    try:
        json_comment = json.loads(''.join(lines))
        if 'swagger' in json_comment:
            return json_comment
    except ValueError:
        # not a swaggerlet
        pass
    return None

class SwaggerCellParser(LoggingConfigurable):
    """A utility class for parsing Jupyter code cells to find API annotations
    of the form:

    `COMMENT (ResponseInfo)? operationId: ID`

    where:

    * `COMMENT` is the single line comment character of the notebook kernel
        language
    * `ResponseInfo` is a literal token.
    * `ID` is an operation's ID as documented in a Swagger comment block
    * `operationId` is a literal token.

    Parameters
    ----------
    comment_prefix
        Token indicating a comment in the notebook language

    Attributes
    ----------
   notebook_cells : list
        The cells from the target notebook, one of which must contain a Swagger spec in a commented block
    operation_indicator : str
        Regex pattern for API annotations
    operation_response_indicator : str
        Regex pattern for API response metadata annotations
    """
    operation_indicator = r'{}\s*operationId:\s*(.*)'
    operation_response_indicator = r'{}\s*ResponseInfo\s+operationId:\s*(.*)'
    notebook_cells = []

    def __init__(self, comment_prefix, *args, **kwargs):
        super(SwaggerCellParser, self).__init__(*args, **kwargs)
        self.kernelspec_operation_indicator = re.compile(self.operation_indicator.format(comment_prefix))
        self.kernelspec_operation_response_indicator = re.compile(self.operation_response_indicator.format(comment_prefix))
        self.swagger = dict()
        operationIdsFound = []
        operationIdsDeclared = []
        for cell in self.notebook_cells:
            if 'type' not in cell or cell['type'] == 'markdown':
                json_swagger = _swaggerlet_from_markdown(cell['source'])
                if json_swagger is not None:
                    self.swagger.update(dict(json_swagger))
            if 'type' not in cell or cell['type'] == 'code':
                match = self.kernelspec_operation_indicator.match(cell['source'])
                if match is not None:
                    operationIdsFound.append(match.group(1).strip())
        if len(self.swagger.values()) == 0:
            self.log.warning('No Swagger documentation found')
        if 'paths' in self.swagger:
            for endpoint in self.swagger['paths'].keys():
                for verb in self.swagger['paths'][endpoint].keys():
                    if 'operationId' in self.swagger['paths'][endpoint][verb]:
                        operationId = self.swagger['paths'][endpoint][verb]['operationId']
                        operationIdsDeclared.append(operationId)
            for operationId in operationIdsDeclared:
                if operationId not in operationIdsFound:
                    self.log.warning('Operation {} was declared but not referenced in a cell'.format(operationId))
            for operationId in operationIdsFound:
                if operationId not in operationIdsDeclared:
                    self.log.warning('Operation {} was referenced in a cell but not declared'.format(operationId))
        else:
            self.log.warning('No paths documented in Swagger documentation')

    def is_api_cell(self, cell_source):
        """Gets if the cell source is documented as an API endpoint.

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        bool
            True if cell is annotated as an API endpoint, or is itself
            a swaggerlet.
        """
        match = self.kernelspec_operation_indicator.match(cell_source)
        return match is not None

    def is_api_response_cell(self, cell_source):
        """Gets if the cell source is annotated as defining API response
        metadata.

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        bool
            True if cell is annotated as ResponseInfo
        """
        match = self.kernelspec_operation_response_indicator.match(cell_source)
        return match is not None

    def endpoints(self, source_cells, sort_func=first_path_param_index):
        """Gets the list of all annotated endpoint HTTP paths and verbs.

        Parameters
        ----------
        source_cells
            List of source strings from notebook cells
        sort_func
            Function by which to sort the endpoint list

        Returns
        -------
        list
            List of tuples with the endpoint str as the first element of each
            tuple and a dict mapping HTTP verbs to cell sources as the second
            element of each tuple
        """
        endpoints = self._endpoint_verb_source_mappings(source_cells, self.kernelspec_operation_indicator)
        sorted_keys = sorted(endpoints, key=sort_func, reverse=True)
        return [(key, endpoints[key]) for key in sorted_keys]

    def endpoint_responses(self, source_cells, sort_func=first_path_param_index):
        """Gets the list of all annotated ResponseInfo HTTP paths and verbs.

        Parameters
        ----------
        source_cells
            List of source strings from notebook cells
        sort_func
            Function by which to sort the endpoint list

        Returns
        -------
        list
            List of tuples with the endpoint str as the first element of each
            tuple and a dict mapping HTTP verbs to cell sources as the second
            element of each tuple
        """
        endpoints = self._endpoint_verb_source_mappings(source_cells, self.kernelspec_operation_response_indicator)
        sorted_keys = sorted(endpoints, key=sort_func, reverse=True)
        return [(key, endpoints[key]) for key in sorted_keys]

    def _endpoint_verb_source_mappings(self, source_cells, operationIdRegex):
        """Gets a dict of all paths, verbs, and contents for the given cells,
        using the given regex to find the relevant operationIds.

        Parameters
        ----------
        source_cells
            List of source strings from notebook cells
        operationIdRegex
            Regex for spotting a cell marked up with a match group that yields
            a Swagger operationId.

        Returns
        -------
        dict
            Dict of dicts mapping the endpoint str to a HTTP verbs to concatenated
            cell sources
        """
        mappings = {}
        operationIds = {}
        # find all of the mentioned operationIds and their concatenated source
        for cell_source in source_cells:
            matched = operationIdRegex.match(cell_source)
            if matched is not None:
                operationId = matched.group(1).strip()
                # stripping trailing whitespace, could be a gotcha
                operationIds.setdefault(operationId, '')
                operationIds[operationId] += cell_source + '\n'

        # go through the declared swagger and assign source values per referenced operationIds
        for endpoint in self.swagger['paths'].keys():
            for verb in self.swagger['paths'][endpoint].keys():
                if 'operationId' in self.swagger['paths'][endpoint][verb] and self.swagger['paths'][endpoint][verb]['operationId'] in operationIds:
                    operationId = self.swagger['paths'][endpoint][verb]['operationId']
                    if 'parameters' in self.swagger['paths'][endpoint][verb]:
                        endpoint_with_param = endpoint
                        ## do we need to sort these names as well?
                        for parameter in self.swagger['paths'][endpoint][verb]['parameters']:
                            if 'name' in parameter:
                                endpoint_with_param = '/:'.join([endpoint_with_param, parameter['name']])
                        mappings.setdefault(endpoint_with_param, {}).setdefault(verb, '')
                        mappings[endpoint_with_param][verb] = operationIds[operationId]
                    else:
                        mappings.setdefault(endpoint, {}).setdefault(verb, '')
                        mappings[endpoint][verb] = operationIds[operationId]
        return mappings

    def get_cell_endpoint_and_verb(self, cell_source):
        """Gets the HTTP path and verb from an annotated cell.

        If the cell is not annotated with an operationId, or the known Swagger
        doc doesn't reference the same operationId, returns (None, None)

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        tuple
            Endpoint str, HTTP verb str
        """
        matched = self.kernelspec_operation_indicator.match(cell_source)
        if matched is not None:
            operationId = matched.group(1)
            # go through the declared operationIds to find corresponding endpoints, methods, and parameters
            for endpoint in self.swagger['paths'].keys():
                for verb in self.swagger['paths'][endpoint].keys():
                    if 'operationId' in self.swagger['paths'][endpoint][verb] and self.swagger['paths'][endpoint][verb]['operationId'] == operationId:
                        return (endpoint, verb)
        return (None, None)

    def get_path_content(self, cell_source):
        """Gets the operation description for an API cell annotation.

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        Object describing the supported operation. If the cell is not annotated,
        just minimal response output guidance.
        """
        matched = self.kernelspec_operation_indicator.match(cell_source)
        operationId = matched.group(1)
        # go through the declared operationIds to find corresponding endpoints, methods, and parameters
        for endpoint in self.swagger['paths'].keys():
            for verb in self.swagger['paths'][endpoint].keys():
                if 'operationId' in self.swagger['paths'][endpoint][verb] and self.swagger['paths'][endpoint][verb]['operationId'] == operationId:
                    return self.swagger['paths'][endpoint][verb]
        # mismatched operationId? return a default
        return {
            'responses': {
                200: {'description': 'Success'}
            }
        }

    def get_default_api_spec(self):
        """Gets the default minimum API spec to use when building a full spec
        from the seed notebook's contents, preferably tak

        dictionary
            Dictionary with a root "swagger" property
        """
        if self.swagger is not None:
            return self.swagger
        return {'swagger': '2.0', 'paths': {}, 'info': {'version': '0.0.0', 'title': 'Default Title'}}

def create_parser(*args, **kwargs):
    return SwaggerCellParser(*args, **kwargs)
