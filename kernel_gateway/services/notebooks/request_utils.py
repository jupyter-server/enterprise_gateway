# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
import re

_named_param_regex = re.compile('(:([^/\s]*))')

def parameterize_path(path):
    matches = re.findall(_named_param_regex, path)
    for match in matches:
        path = path.replace(match[0], '(?P<{}>[^\/]+)'.format(match[1]))
    return path.strip()

def parse_body(body):
    '''Converts body into a proper JSON string. body is expected to be a UTF-8
    byte string. If body is the empty string or None, the empty string will be
    returned.
    '''
    body = None if body is b'' else body.decode(encoding='UTF-8')
    if body is not None:
        return json.loads(body)
    else:
        return ''

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
