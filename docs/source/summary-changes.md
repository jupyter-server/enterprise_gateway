# Summary of changes

See `git log` for a more detailed summary of changes.

## 0.6

## 0.6.0 (2016-XX-XX)

* Add `--KernelGateway.port_retries` option like in Jupyter Notebook

## 0.5

### 0.5.0 (2016-04-04)

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

## 0.4
### 0.4.0 (2016-02-17)

* Enable `/_api/activity` resource with stats about kernels in
  `jupyter-websocket` mode
* Enable `/api/sessions` resource with in-memory name-to-kernel mapping for
  non-notebook clients that want to look-up kernels by associated session name
* Fix prespawn kernel logic regression for `jupyter-websocket` mode
* Fix all handlers so that they return application/json responses on error
* Fix missing output from cells that emit display data in `notebook-http` mode

## 0.3
### 0.3.1 (2016-01-25)

* Fix CORS and auth token headers for `/_api/spec/swagger.json` resource
* Fix `allow_origin` handling for non-browser clients
* Ensure base path is prefixed with a forward slash
* Filter stderr from all responses in `notebook-http` mode
* Set Tornado logging level and Jupyter logging level together with
  `--log-level`

### 0.3.0 (2016-01-15)

* Support setting of status and headers in `notebook-http` mode
* Support automatic, minimal Swagger doc generation in `notebook-http` mode
* Support download of a notebook in `notebook-http` mode
* Support CORS and token auth in `notebook-http` mode
* Expose HTTP request headers in `notebook-http` mode
* Support multipart form encoding in `notebook-http` mode
* Fix request value JSON encoding when passing requests to kernels
* Fix kernel name handling when pre-spawning
* Fix lack of access logs in `notebook-http` mode

## 0.2
### 0.2.0 (2015-12-15)

* Support notebook-defined HTTP APIs on a pool of kernels
* Disable kernel instance list by default

## 0.1
### 0.1.0 (2015-11-18)

* Support Jupyter Notebook kernel CRUD APIs and Jupyter kernel protocol over
  Websockets
* Support shared token auth
* Support CORS headers
* Support base URL
* Support seeding kernels code from a notebook at a file path or URL
* Support default kernel, kernel pre-spawning, and kernel count limit
* First PyPI release
