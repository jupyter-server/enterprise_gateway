## Features

The Jupyter Kernel Gateway has the following features:

* [`jupyter-websocket` mode](websocket-mode) which provides a 
  Jupyter Notebook server-compatible API for requesting kernels and
  communicating with them using Websockets
* [`notebook-http` mode](http-mode) which maps HTTP requests to
  cells in annotated notebooks
* Option to enable other kernel communication mechanisms by plugging in third party personalities
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
  in `notebook-http` mode
* Generation of [Swagger specs](http://swagger.io/introducing-the-open-api-initiative/)
  for notebook-defined API in `notebook-http` mode
* A CLI for launching the kernel gateway: `jupyter kernelgateway OPTIONS`
* A Python 2.7 and 3.3+ compatible implementation
