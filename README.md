# Jupyter Kernel Gateway

A [JupyterApp](https://github.com/jupyter/jupyter_core/blob/master/jupyter_core/application.py) that
implements different APIs and protocols for accessing Jupyter kernels such as:

* Accessing HTTP and Websocket resources of `/api/kernels` using [jupyter/notebook](https://github.com/jupyter/notebook), [jupyter/jupyter_client](https://github.com/jupyter/jupyter_client), and [jupyter/jupyter_core](https://github.com/jupyter/jupyter_core).
* [Accessing notebook cells](#notebook-http-mode) via HTTP endpoints

The app launches kernels in its local process/filesystem space. Can be containerized and scaled out by a cluster manager (e.g., [tmpnb](https://github.com/juputer/tmpnb)). API endpoints can be accessed by [jupyter-js-services](https://github.com/jupyter/jupyter-js-services) and similar web-friendly clients.

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

## NodeJS Client Example

The following sample uses the new `jupyter-js-services` npm package to request a kernel from a kernel gateway and execute some code on it. You can find this sample in `etc/node_client_example` in this repo along with a `package.json` file that installs all the client dependencies (i.e., run `npm install` then `node client.js`).

```javascript
var xmlhttprequest = require('xmlhttprequest');
var ws = require('ws');

global.XMLHttpRequest = xmlhttprequest.XMLHttpRequest;
global.WebSocket = ws;

var jupyter = require('jupyter-js-services');

var kg_host = process.env.GATEWAY_HOST || '192.168.99.100:8888';

// get info about the available kernels and start a new one
jupyter.getKernelSpecs('http://'+kg_host).then((kernelSpecs) => {
    console.log('Available kernelspecs:', kernelSpecs);
    var options = {
        baseUrl: 'http://'+kg_host,
        wsUrl: 'ws://'+kg_host,
        name: kernelSpecs.default
    };
    // request a kernel in the default language (python)
    jupyter.startNewKernel(options).then((kernel) => {
        // execute some code
        var future = kernel.execute({ code: 'print("Hello world!")' } );
        future.onDone = () => {
            // quit when done
            process.exit(0);
        };
        future.onIOPub = (msg) => {
            // print received messages
            console.log('Received message type:', msg.msg_type);
            if(msg.msg_type === 'stream') {
                console.log('  Content:', msg.content.text);
            }
        };
    });
});
```

## Python Client Example

The following code shows how to request a kernel and execute code on it using the Tornado HTTP and Websocket client library. You can find this sample in `etc/python_client_example` in this repo.

The code here is much longer than in the NodeJS case above because there isn't a Python equivalent of `jupyter-js-services` that wraps the logic for talking the Jupyter protocol over over Websockets. (Of course, there is [jupyter/jupyter_client](https://github.com/jupyter/jupyter_client) which operates over ZeroMQ.)

```python
import os
from tornado import gen
from tornado.escape import json_encode, json_decode, url_escape
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado.httpclient import AsyncHTTPClient

@gen.coroutine
def main():
    kg_host = os.getenv('GATEWAY_HOST', '192.168.99.100:8888')

    client = AsyncHTTPClient()

    response = yield client.fetch(
        'http://{}/api/kernels'.format(kg_host),
        method='POST',
        body='{}'
    )
    print('Created kernel')
    kernel = json_decode(response.body)
    print(kernel)

    ws_url = 'ws://{}/api/kernels/{}/channels'.format(
        kg_host,
        url_escape(kernel['id'])
    )
    ws = yield websocket_connect(ws_url)
    print('Connected to kernel websocket')

    # Send an execute request
    ws.write_message(json_encode({
        'header': {
            'username': '',
            'version': '5.0',
            'session': '',
            'msg_id': 'test-msg',
            'msg_type': 'execute_request'
        },
        'parent_header': {},
        'channel': 'shell',
        'content': {
            'code': 'print("Hello world!")',
            'silent': False,
            'store_history': False,
            'user_expressions' : {}
        },
        'metadata': {},
        'buffers': {}
    }))

    # Look for stream output for the print in the execute
    while 1:
        msg = yield ws.read_message()
        msg = json_decode(msg)
        msg_type = msg['msg_type']
        print('Received message type:', msg_type)
        parent_msg_id = msg['parent_header']['msg_id']
        if msg_type == 'stream' and parent_msg_id == 'test-msg':
            print('  Content:', msg['content']['text'])
            break

    ws.close()

if __name__ == '__main__':
    IOLoop.current().run_sync(main)
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

###Body And Content Type
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
