# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""CLI entrypoint for the kernel gateway package."""
from __future__ import absolute_import

if __name__ == '__main__':
    import elyra.elyraapp as app
    app.launch_instance()
