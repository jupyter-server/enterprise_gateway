# Jupyter Kernel Gateway

A [JupyterApp](https://github.com/jupyter/jupyter_core/blob/master/jupyter_core/application.py) that implements the HTTP and Websocket resources of `/api/kernels` using [jupyter/notebook](https://github.com/jupyter/notebook), [jupyter/jupyter_client](https://github.com/jupyter/jupyter_client), and [jupyter/jupyter_core](https://github.com/jupyter/jupyter_core) as libraries. Launches kernels in its local process/filesystem space. Can be containerized and scaled out by a cluster manager (e.g., [tmpnb](https://github.com/juputer/tmpnb)). Intended to be accessed by [jupyter-js-services](https://github.com/jupyter/jupyter-js-services) and similar web-friendly clients.

## Interesting Uses

* Attach a local Jupyter Notebook server to a compute cluster in the cloud running near big data (e.g., interactive gateway to Spark)
* Enable a new breed of non-notebook web clients to provision and use kernels (e.g., dashboards)
* Scale kernels independently from clients (e.g., via [tmpnb](https://github.com/jupyter/tmpnb), [Binder](https://mybinder.org), your favorite cluster manager)

![Example diagram of how tmpnb might deploy kernel gateway + kernel containers](etc/tmpnb_kernel_gateway.png)

## What It Gives You

* Python 3 implementation of the following resources equivalent to the ones found in the latest Jupyter Notebook code base:
    * `/api` (metadata)
    * `/api/kernelspecs` (what kernels are available)
    * `/api/kernels` (kernel CRUD)
* A way to bridge the [Jupyter protocol](http://jupyter-client.readthedocs.org/en/latest/messaging.html) from Websocket to [ZeroMQ](http://zeromq.org/)
* A shared token authorization scheme
* CORS headers as options for servicing browser-based clients
* Ability to set a custom base URL (e.g., for running under tmpnb)
* Option to limit the number kernel instances a gateway server will launch (e.g., to force scaling at the container level)
* A CLI for launching the kernel gateway: `jupyter kernelgateway OPTIONS`

## What It Lacks

These are in scope, but not yet implemented.

* PyPI package
* Ability to prespawn kernels
* Ability to select a default kernel
* Ability to prepopulate kernel memory from a notebook

## Alternatives

* A Go-based implementation of a kernel gateway has also been proposed (e.g., using [rgbkrk/juno](https://github.com/rgbkrk/juno)). It will have the benefit of being a single binary that can be dropped into any environment more easily than a full Python-stack. A potential downside is that it will need to track changes in the Jupyter API and protocols whereas the Python implementation here does so implicitly.
* If your client is within the same compute cluster as the kernel and already has good ZeroMQ support, there is no need to use the kernel gateway to enable Websocket access. Talk ZeroMQ directly to the kernel.

## Try It

TODO: We're working on a PyPI package and/or Docker image. For now, if you want to install without Docker, you'll need to clone and install from the git repo.

```
git clone https://github.com/jupyter-incubator/kernel_gateway.git
cd kernel_gateway
# install from clone
pip install .
# show all config options
jupyter kernelgateway --help-all
# run it with default options
jupyter kernelgateway
```

## NodeJS Client Example

The following sample uses the new `jupyter-js-services` npm package to request a kernel from a kernel gateway and execute some code on it. You can find this sample in `etc/node_client_example` in this repo along with a `package.json` file that installs all the client dependencies (i.e., run `npm install` then `node client.js`).

```
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

```
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

## Develop

This repository is setup for a Dockerized development environment. On a Mac, do this one-time setup if you don't have a local Docker environment yet.

```
brew update

# make sure you're on Docker >= 1.7
brew install docker-machine docker
docker-machine create -d virtualbox dev
eval "$(docker-machine env dev)"
```

Pull the Docker image that we'll use for development. We currently use the `jupyter/minimal-notebook:4.0` image because it has all the dependencies preinstalled, but it includes far more than we really need.

```
docker pull jupyter/minimal-notebook:4.0
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
make test
```

Run the gateway server:

```
cd kernel_gateway
make dev
```

To access the gateway instance:

1. Run `docker-machine ls` and note the IP of the dev machine.
2. Visit http://THAT_IP:8888/api/kernels in your browser