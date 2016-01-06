# Jupyter Kernel Gateway

A [JupyterApp](https://github.com/jupyter/jupyter_core/blob/master/jupyter_core/application.py) that
implements different APIs and protocols for accessing Jupyter kernels such as:

* Accessing HTTP and Websocket resources of `/api/kernels` using [jupyter/notebook](https://github.com/jupyter/notebook), [jupyter/jupyter_client](https://github.com/jupyter/jupyter_client), and [jupyter/jupyter_core](https://github.com/jupyter/jupyter_core).
* [Accessing notebook cells](#notebook-http-mode) via HTTP endpoints

The app launches kernels in its local process/filesystem space. Can be containerized and scaled out by a cluster manager (e.g., [tmpnb](https://github.com/jupyter/tmpnb)). API endpoints can be accessed by [jupyter-js-services](https://github.com/jupyter/jupyter-js-services) and similar web-friendly clients.

## Interesting Uses

* Attach a local Jupyter Notebook server to a compute cluster in the cloud running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use kernels (e.g., dashboards)
* Scale kernels independently from clients (e.g., via [tmpnb](https://github.com/jupyter/tmpnb), [Binder](https://mybinder.org), your favorite cluster manager)
* Creating microservices from notebooks via [`notebook-http` mode](#notebook-http-mode)

![Example diagram of how tmpnb might deploy kernel gateway + kernel containers](etc/tmpnb_kernel_gateway.png)

## What It Gives You

* Python 2.7 and 3.3+ compatible implementation of the following resources, equivalent to the ones found in the latest Jupyter Notebook 4.x code base:
    * `/api` (metadata)
    * `/api/kernelspecs` (what kernels are available)
    * `/api/kernels` (kernel CRUD)
    * `/api/kernels/:kernel_id/channels` (Websocket-to-[ZeroMQ](http://zeromq.org/) transformer for the [Jupyter kernel protocol](http://jupyter-client.readthedocs.org/en/latest/messaging.html))
* Option to set a shared authentication token and require it from clients
* Option to set CORS headers for servicing browser-based clients
* Option to set a custom base URL (e.g., for running under tmpnb)
* Option to limit the number kernel instances a gateway server will launch (e.g., to force scaling at the container level)
* Option to prespawn a set number of kernels
* Option to set a default kernel language
* Option to prepopulate kernel memory from a notebook
* A CLI for launching the kernel gateway: `jupyter kernelgateway OPTIONS`
* Option to serve annotated notebooks as HTTP endpoints, see [notebook-http](#notebook-http-mode)
* Option to allow downloading of the notebook source when running notebook-http-mode

Run `jupyter kernelgateway --help-all` after installation to see the full set of options.

## Try It

```
# install from pypi
pip install jupyter_kernel_gateway
# show all config options
jupyter kernelgateway --help-all
# run it with default options
jupyter kernelgateway
```

## `notebook-http` Mode

The `KernelGatewayApp.api` command line argument can be set to `notebook-http`
to allow a properly annotated notebook to be served via HTTP endpoints. A
notebook cell must be annotated with a single line comment at the beginning
describing the HTTP endpoint. An example python cell is:

```python
# GET /hello/world
print("hello world")
```

This enables an HTTP GET on `/hello/world`. The [api_intro.ipynb](https://github.com/jupyter-incubator/kernel_gateway/blob/master/etc/api_examples/api_intro.ipynb)
provides a full example notebook for reference.

The comment syntax should be supported in every language, but it is a work in
progress to identify all supported syntaxes.

### Processing requests

When your cell is invoked there will be a string variable called `REQUEST`
available in the scope of your cell's code. If your kernel's language requires
variable declarations, you will need to explicitly define the `REQUEST` variable
in your notebook. This string is a JSON object representing various properties
of the request. You will need to parse this string to access the properties.
For example, in python:

```python
# GET /hello/world
req = json.loads(REQUEST)
# do something with req
```

Path parameters can be specified when registering an endpoint by appending a `:`
to a value within the path. For example, in python a path with path params
`firstName` and `lastName` would be defined as:

```python
# GET /hello/:firstName/:lastName
```

The REQUEST object currently contains the following properties:

* `body` - The value of the body, see the [Body And Content Type](#Body-And-Content-Type) section below
* `args` - An object with keys representing query parameter names and their associated values. A query parameter name may be specified multiple times in a valid URL, and so each value is a sequence (e.g., list, array) of strings from the original URL.
* `path` - An object of key-value pairs representing path parameters and
their values.
* `headers` - An object of key-value pairs where a key is a HTTP header name and a value is the HTTP header value. If there are multiple values are specified for a  header, the value will be an array.

### Body And Content Type
If the HTTP request to the kernel gateway has a `Content-Type` header the `REQUEST.body` value may change. Below is the list of outcomes for various mime-types:

* `application/json` -  The `REQUEST.body` will be an object of key-value pairs representing the request body
* `multipart/form-data` and `application/x-www-form-urlencoded` -  The `REQUEST.body` will be an object of key-value pairs representing the parameters and their values. Files are currently not supported for `multipart/form-data`
* `text/plain` -  The `REQUEST.body` will be the string value of the body
* All other types will be sent as strings

### Setting The Response

The response for HTTP mode can be set in two ways:
1. Writing to standard out
1. A map containing a key-value pairs of mime-type to value

The first method is preferred and is language dependent (e.g. python `print`,
Scala `println`, R `print`). All standard output during your cell's execution
will be collected and returned verbatim as the response.

The second approach is used if no output is collected. This method is dependent
upon language semantics, kernel implementation, and library usage. The return
value will be the `content.data` in the Jupyter [`execute_result`](http://jupyter-client.readthedocs.org/en/latest/messaging.html#id4)
message.

### Running
The minimum number of arguments needed to run in HTTP mode are
`--KernelGatewayApp.api=notebook-http` and
`--KernelGatewayApp.seed_uri=some/notebook/file.ipynb`.

You can run the kernel gateway in `notebook-http` mode from the Makefile:

```
make dev ARGS="--KernelGatewayApp.api='notebook-http' \
--KernelGatewayApp.seed_uri=/srv/kernel_gateway/etc/api_examples/scotch_api.ipynb"
```

With the above Make command, all of the notebooks in `etc/api_examples` are
mounted into `/srv/kernel_gateway/etc/api_examples/` and can be run in HTTP mode.

The notebook-http mode will honor the `prespawn_count` command line argument.
This will start the specified number of kernels and execute the `seed_uri`
notebook across all of them. Requests will be distributed across all of the
spawned kernels, providing a minimal layer of scalability. An example which
starts 5 kernels:

```
make dev ARGS="--KernelGatewayApp.api='notebook-http' \
--KernelGatewayApp.seed_uri=/srv/kernel_gateway/etc/api_examples/scotch_api.ipynb" \
--KernelGatewayApp.prespawn_count=5
```

## Kernel Gateway Demos
For a complete set of demos utilizing the default jupyter-websocket and alternative notebook-http modes see
[Kernel Gateway Demos](https://github.com/jupyter-incubator/kernel_gateway_demos).

## Alternatives

* A Go-based implementation of a kernel gateway has also been proposed (e.g., using [rgbkrk/juno](https://github.com/rgbkrk/juno)). It will have the benefit of being a single binary that can be dropped into any environment more easily than a full Python-stack. A potential downside is that it will need to track changes in the Jupyter API and protocols whereas the Python implementation here does so implicitly.
* If your client is within the same compute cluster as the kernel and already has good ZeroMQ support, there is no need to use the kernel gateway to enable Websocket access. Talk ZeroMQ directly to the kernel.

## Develop

This repository is setup for a Dockerized development environment. On a Mac, do this one-time setup if you don't have a local Docker environment yet.

```
brew update

# make sure you're on Docker >= 1.7
brew install docker-machine docker
docker-machine create -d virtualbox dev
eval "$(docker-machine env dev)"
```

Clone this repository in a local directory that docker can volume mount:

```
# make a directory under ~ to put source
mkdir -p ~/projects
cd !$

# clone this repo
git clone https://github.com/jupyter-incubator/kernel_gateway.git
```

Run the tests:

```
make test-python3
make test-python2
```

Run the gateway server:

```
cd kernel_gateway
make dev
```

To access the gateway instance:

1. Run `docker-machine ls` and note the IP of the dev machine.
2. Visit http://THAT_IP:8888/api/kernels in your browser
