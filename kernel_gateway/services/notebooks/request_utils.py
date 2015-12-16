# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
import re
from tornado.httputil import parse_body_arguments

_named_param_regex = re.compile('(:([^/\s]*))')
FORM_URLENCODED = 'application/x-www-form-urlencoded'
MULTIPART_FORM_DATA = 'multipart/form-data'
APPLICATION_JSON = 'application/json'
TEXT_PLAIN = 'text/plain'

def parameterize_path(path):
    matches = re.findall(_named_param_regex, path)
    for match in matches:
        path = path.replace(match[0], '(?P<{}>[^\/]+)'.format(match[1]))
    return path.strip()

def parse_body(request):
    '''Takes an HTTP request and will parse the body depending on the Content-Type
    header. If no Content-Type is found, will treat the value as plain text. The
    return value is a dict or string representing the body.
    '''
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
    '''Converts args into a proper JSON string. args is expected to be a dictionary
    where the values are arrays of UTF-8 byte strings.
    '''
    ARGS = {}
    for key in args:
        ARGS[key] = []
        for value in args[key]:
            ARGS[key].append(value.decode(encoding='UTF-8'))
    return ARGS
