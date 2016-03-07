# Jupyter Kernel Gateway

A web server that supports different mechanisms for spawning and
communicating with Jupyter kernels, such as:

* A Jupyter Notebook server-compatible HTTP API used for requesting kernels
  and talking the [Jupyter kernel protocol](http://jupyter-client.readthedocs.org/en/latest/messaging.html)
  with the kernels over Websockets
* A HTTP API defined by annotated notebook cells that maps HTTP verbs and
  resources to code to execute on a kernel

The server launches kernels in the server's local process/filesystem space.
The server can be containerized and scaled out by a cluster manager (e.g.,
[tmpnb](https://github.com/jupyter/tmpnb)).

## Installation

Detailed installation can be found in the 
[Jupyter Kernel Gateway documentation]()
found on ReadTheDocs.




## Contributors

### Setting up a development system
