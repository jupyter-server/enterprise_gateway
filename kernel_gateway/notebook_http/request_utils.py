# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Utilities for handling HTTP requests."""

import json
import re
from tornado.httputil import parse_body_arguments

_named_param_regex = re.compile('(:([^/\s]*))')
FORM_URLENCODED = 'application/x-www-form-urlencoded'
MULTIPART_FORM_DATA = 'multipart/form-data'
APPLICATION_JSON = 'application/json'
TEXT_PLAIN = 'text/plain'

def format_request(bundle):
    """Creates an assignment statement of bundle JSON-encoded to a variable
    named `REQUEST`.

    Returns
    -------
    str
        `REQUEST = "<json-encoded expression>"`
    """
    bundle = json.dumps(bundle)
    statement = "REQUEST = {}".format(bundle)
    return statement

def parameterize_path(path):
    """Creates a regex to match all named parameters in a path.

    Parameters
    ----------
    path : str
        URL path with `/:name` segments

    Returns
    -------
    str
        Path with `:name` parameters replaced with regex patterns for matching
        them.
    """
    matches = re.findall(_named_param_regex, path)
    for match in matches:
        path = path.replace(match[0], '(?P<{}>[^\/]+)'.format(match[1]))
    return path.strip()

def parse_body(request):
    """Parses the body of an HTTP request based on its Content-Type.

    If no Content-Type is found, treats the value as plain text.

    Parameters
    ----------
    request : tornado.web.HTTPRequest
        Web request with the body to parse

    Returns
    -------
    dict or str
        Dictionary of a form-encoded JSON-encoded body, raw string otherwise
    """
    content_type = TEXT_PLAIN
    body = request.body
    body = '' if body is b'' or body is None else body.decode(encoding='UTF-8')
    if 'Content-Type' in request.headers:
        content_type = request.headers['Content-Type']
    return_body = body
    if content_type == FORM_URLENCODED or content_type.startswith(MULTIPART_FORM_DATA):
        # If there is form data, we already have the values in body_arguments, we
        # just need to convert the byte arrays to strings
        return_body = parse_args(request.body_arguments)
    elif content_type == APPLICATION_JSON:
        # Trying parsing the json, if we can't parse it the initial assignment
        # will treat the body as text
        try:
            return_body = json.loads(body)
        except Exception:
            pass
    return return_body

def parse_args(args):
    """Decodes UTF-8 encoded argument values.

    Parameters
    ----------
    args : dict
        Maps arbitrary keys to UTF-8 encoded strings / byte-arrays

    Returns
    -------
    dict
        Maps keys from args to decoded strings
    """
    rv = {}
    for key in args:
        rv[key] = []
        for value in args[key]:
            rv[key].append(value.decode(encoding='UTF-8'))
    return rv

def headers_to_dict(headers):
    """Turns a set of tornado headers into a Python dict.

    Repeat headers are aggregated into lists.

    Parameters
    ----------
    headers : dict
        Key / value header pairs

    Returns
    -------
    dict
        Maps keys from headers to values or lists of values
    """
    new_headers = {}
    for header, header_value in headers.get_all():
        if header in new_headers:
            if not isinstance(new_headers[header], list):
                original_value = new_headers[header]
                new_headers[header] = [original_value]
            new_headers[header].append(header_value)
        else:
            new_headers[header] = header_value

    return new_headers
