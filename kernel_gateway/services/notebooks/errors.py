# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
class CodeExecutionError(Exception):
    def __init__(self, error_message):
        self.error_message = error_message

class UnsupportedMethodError(Exception):
    def __init__(self, method):
        self.method = method
