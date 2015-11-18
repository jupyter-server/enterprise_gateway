// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

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
