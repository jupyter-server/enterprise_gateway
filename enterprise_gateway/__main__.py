# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""CLI entrypoint for the enterprise gateway package."""

if __name__ == "__main__":
    import enterprise_gateway.enterprisegatewayapp as app

    app.launch_instance()
