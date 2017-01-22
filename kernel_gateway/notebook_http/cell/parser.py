# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Simple parser for notebook cell API annotations."""

import re
import sys
from traitlets.config.configurable import LoggingConfigurable

def first_path_param_index(endpoint):
    """Gets the index to the first path parameter for the endpoint. The
    returned value is not the string index, but rather the depth of where the
    endpoint is found in the the path.

    Parameters
    ---------
    endpoint : str
        URL

    Returns
    -------
    int
        Path segment index value or sys.maxsize

    Examples
    --------

    >>> first_path_param_index('/foo/:bar')
    1
    >>> first_path_param_index('/foo/quo/:bar')
    2
    >>> first_path_param_index('/foo/quo/bar')
    sys.maxsize
    """
    index = sys.maxsize
    if endpoint.find(':') >= 0:
        index = endpoint.count('/', 0, endpoint.find(':')) - 1
    return index

class APICellParser(LoggingConfigurable):
    """A utility class for parsing Jupyter code cells to find API annotations
    of the form:

    `COMMENT (ResponseInfo)? HTTP_VERB URL_PATH`

    where:

    * `COMMENT` is the single line comment character of the notebook kernel
        language
    * `HTTP_VERB` is a valid HTTP verb
    * `URL_PATH` is a valid HTTP URL path string with optional `:variable`
        placeholders
    * `ResponseInfo` is a literal token.

    Parameters
    ----------
    comment_prefix
        Token indicating a comment in the notebook language

    Attributes
    ----------
    api_indicator : str
        Regex pattern for API annotations
    api_response_indicator : str
        Regex pattern for API response metadata annotations
    """
    api_indicator = r'{}\s+(GET|PUT|POST|DELETE)\s+(\/.*)+'
    api_response_indicator = r'{}\s+ResponseInfo\s+(GET|PUT|POST|DELETE)\s+(\/.*)+'

    def __init__(self, comment_prefix, *args, **kwargs):
        super(APICellParser, self).__init__(*args, **kwargs)
        self.kernelspec_api_indicator = re.compile(self.api_indicator.format(comment_prefix))
        self.kernelspec_api_response_indicator = re.compile(self.api_response_indicator.format(comment_prefix))

    def is_api_cell(self, cell_source):
        """Gets if the cell source is annotated as an API endpoint.

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        bool
            True if cell is annotated as an API endpoint
        """
        match = self.kernelspec_api_indicator.match(cell_source)
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
        match = self.kernelspec_api_response_indicator.match(cell_source)
        return match is not None

    def get_cell_endpoint_and_verb(self, cell_source):
        """Gets the HTTP path and verb from an API cell annotation.

        If the cell is not annotated, returns (None, None)

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        tuple
            Endpoint str, HTTP verb str
        """
        endpoint = None
        verb = None
        matched = self.kernelspec_api_indicator.match(cell_source)
        if matched:
            endpoint = matched.group(2).strip()
            verb = matched.group(1)
        return endpoint, verb

    def get_path_content(self, cell_source):
        """Gets the operation description for an API cell annotation.

        Parameters
        ----------
        cell_source
            Source from a notebook cell

        Returns
        -------
        Object describing the supported operation, at minimum, guidance for
        the eventual response output.
        """
        return {
            'responses': {
                200: {'description': 'Success'}
            }
        }

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
        endpoints = {}
        for cell_source in source_cells:
            if self.is_api_cell(cell_source):
                matched = self.kernelspec_api_indicator.match(cell_source)
                uri = matched.group(2).strip()
                verb = matched.group(1)

                endpoints.setdefault(uri, {}).setdefault(verb, '')
                endpoints[uri][verb] += cell_source + '\n'

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
        endpoints = {}
        for cell_source in source_cells:
            if self.is_api_response_cell(cell_source):
                matched = self.kernelspec_api_response_indicator.match(cell_source)
                uri = matched.group(2).strip()
                verb = matched.group(1)

                endpoints.setdefault(uri, {}).setdefault(verb, '')
                endpoints[uri][verb] += cell_source + '\n'
        return endpoints

    def get_default_api_spec(self):
        """Gets the default minimum API spec to use when building a full spec
        from the seed notebook's contents.

        dictionary
            Dictionary with a root "swagger" property
        """
        return {'swagger': '2.0', 'paths': {}, 'info': {'version': '0.0.0'}}

def create_parser(*args, **kwargs):
    return APICellParser(*args, **kwargs)
