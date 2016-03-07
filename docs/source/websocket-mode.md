## `jupyter-websocket` Mode

The `KernelGatewayApp.api` command line argument defaults to 
`jupyter-websocket`. In this mode, the kernel gateway defines the following
web resources:

* `/api` (metadata)
* `/api/kernelspecs` (what kernels are available)
* `/api/kernels` (kernel CRUD, with discovery disabled by default,
  see `--list_kernels`)
* `/api/kernels/:kernel_id/channels` (Websocket-to-[ZeroMQ](http://zeromq.org/) 
  transformer for the [Jupyter kernel protocol](http://jupyter-client.readthedocs.org/en/latest/messaging.html))
* `/api/sessions` (session CRUD, for associating information with kernels,
  discovery disabled by default, see `--list_kernels`)
* `/_api/activity` (activity metrics for all running kernels, enabled with
  `--list_kernels`)

Discounting features of the kernel gateway (e.g., token auth), the behavior
of these resources is equivalent to that found in the Jupyter Notebook server.
The kernel gateway simply imports and extends the handler classes from
the Jupyter Notebook.