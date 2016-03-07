## Features

The Jupyter Kernel Gateway provides a rich set of features and options:

* [`jupyter-websocket` mode](#jupyter-websocket-mode) which provides a 
  Jupyter Notebook server-compatible API for requesting kernels and
  communicating with them using Websockets
* [`notebook-http` mode](#notebook-http-mode) which maps HTTP requests to
  cells in annotated notebooks
* Option to set a shared authentication token and require it from clients
* Options to set CORS headers for servicing browser-based clients
* Option to set a custom base URL (e.g., for running under tmpnb)
* Option to limit the number kernel instances a gateway server will launch
  (e.g., to force scaling at the container level)
* Option to pre-spawn a set number of kernel instances
* Option to set a default kernel language to use when one is not specified
  in the request
* Option to pre-populate kernel memory from a notebook
* Option to serve annotated notebooks as HTTP endpoints, see
  [notebook-http](#notebook-http-mode)
* Option to allow downloading of the notebook source when running
  `notebook-http` mode
* Automatic [Swagger spec](http://swagger.io/introducing-the-open-api-initiative/)
  for a notebook-defined API in `notebook-http` mode
* A CLI for launching the kernel gateway: `jupyter kernelgateway OPTIONS`
* A Python 2.7 and 3.3+ compatible implementation
