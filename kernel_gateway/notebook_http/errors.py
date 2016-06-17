# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Exception classes for notebook-http mode."""

class CodeExecutionError(Exception):
    """Raised when a notebook's code fails to execute in response to an API
    request.
    """
    pass

class UnsupportedMethodError(Exception):
    """Raised when a notebook-defined API does not support the requested HTTP
    method.
    """
    pass
