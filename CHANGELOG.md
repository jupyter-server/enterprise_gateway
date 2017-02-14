# Changelog

## 1.2.0 (2017-02-12)

* Add command line option to whitelist environment variables for `POST /api/kernels`
* Add support for HTTPS key and certificate files
* Improve the flow and explanations in the `api_intro` notebook
* Fix incorrect use of `metadata.kernelspec.name` as a language name instead of
  `metadata.language.info`
* Fix lingering kernel regression after Ctrl-C interrupt
* Switch to a conda-based dev setup from docker

## 1.1.2 (2016-12-16)

* Fix compatibility with Notebook 4.3 session handler `create_session` call

## 1.1.1 (2016-09-10)

* Add LICENSE file to package distributions

## 1.1.0 (2016-09-08)

* Add an option to force a specific kernel spec for all requests and seed notebooks
* Add support for specifying notebook-http APIs using full Swagger specs
* Add option to serve static web assets from Tornado in notebook-http mode
* Add command line aliases for common options (e.g., `--ip`)
* Fix Tornado 4.4 compatbility: sending an empty body string with a 204 response

## 1.0.0 (2016-07-15)

* Introduce an [API for developing mode plug-ins](https://jupyter-kernel-gateway.readthedocs.io/en/latest/plug-in.html)
* Separate `jupyter-websocket` and `notebook-http` modes into  plug-in packages
* Move mode specific command line options into their respective packages (see `--help-all`)
* Report times with respect to UTC in `/_api/activity` responses

## 0.6.0 (2016-06-17)

* Switch HTTP status from 402 for 403 when server reaches the max kernel limit
* Explicitly shutdown kernels when the server shuts down
* Remove `KG_AUTH_TOKEN` from the environment of kernels
* Fix missing swagger document in release
* Add `--KernelGateway.port_retries` option like in Jupyter Notebook
* Fix compatibility with Notebook 4.2 session handler `create_session` call

## 0.5.1 (2016-04-20)

* Backport `--KernelGateway.port_retries` option like in Jupyter Notebook
* Fix compatibility with Notebook 4.2 session handler `create_session` call

## 0.5.0 (2016-04-04)

* Support multiple cells per path in `notebook-http` mode
* Add a Swagger specification of the `jupyter-websocket` API
* Add `KERNEL_GATEWAY=1` to all kernel environments
* Support environment variables in `POST /api/kernels`
* numpydoc format docstrings on everything
* Convert README to Sphinx/ReadTheDocs site
* Convert `ActivityManager` to a traitlets `LoggingConfigurable`
* Fix `base_url` handling for all paths
* Fix unbounded growth of ignored kernels in `ActivityManager`
* Fix caching of Swagger spec in `notebook-http` mode
* Fix failure to install due to whitespace in `setup.py` version numbers
* Fix call to kernel manager base class when starting a kernel
* Fix test fixture hangs

## 0.4.1 (2016-04-20)

* Backport `--KernelGateway.port_retries` option like in Jupyter Notebook
* Fix compatibility with Notebook 4.2 session handler `create_session` call

## 0.4.0 (2016-02-17)

* Enable `/_api/activity` resource with stats about kernels in `jupyter-websocket` mode
* Enable `/api/sessions` resource with in-memory name-to-kernel mapping for non-notebook clients that want to look-up kernels by associated session name
* Fix prespawn kernel logic regression for `jupyter-websocket` mode
* Fix all handlers so that they return application/json responses on error
* Fix missing output from cells that emit display data in `notebook-http` mode

## 0.3.1 (2016-01-25)

* Fix CORS and auth token headers for `/_api/spec/swagger.json` resource
* Fix `allow_origin` handling for non-browser clients
* Ensure base path is prefixed with a forward slash
* Filter stderr from all responses in `notebook-http` mode
* Set Tornado logging level and Jupyter logging level together with `--log-level`

## 0.3.0 (2016-01-15)

* Support setting of status and headers in `notebook-http` mode
* Support automatic, minimal Swagger doc generation in `notebook-http` mode
* Support download of a notebook in `notebook-http` mode
* Support CORS and token auth in `notebook-http` mode
* Expose HTTP request headers in `notebook-http` mode
* Support multipart form encoding in `notebook-http` mode
* Fix request value JSON encoding when passing requests to kernels
* Fix kernel name handling when pre-spawning
* Fix lack of access logs in `notebook-http` mode

## 0.2.0 (2015-12-15)

* Support notebook-defined HTTP APIs on a pool of kernels
* Disable kernel instance list by default

## 0.1.0 (2015-11-18)

* Support Jupyter Notebook kernel CRUD APIs and Jupyter kernel protocol over Websockets
* Support shared token auth
* Support CORS headers
* Support base URL
* Support seeding kernels code from a notebook at a file path or URL
* Support default kernel, kernel pre-spawning, and kernel count limit
* First PyPI release
