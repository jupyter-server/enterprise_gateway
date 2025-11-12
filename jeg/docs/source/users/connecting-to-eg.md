# Connecting the server to Enterprise Gateway

To leverage the benefits of Enterprise Gateway, it's helpful to redirect a Jupyter server's kernel management to the Gateway server. This allows better separation of the user's notebooks from the managed computer cluster (Kubernetes, Hadoop YARN, Docker Swarm, etc.) on which Enterprise Gateway resides. A Jupyter server can be configured to relay kernel requests to an Enterprise Gateway server in several ways.

## Command line

To instruct the server to connect to an Enterprise Gateway instance running on host `<EG_HOST_IP>` on port `<EG_PORT>`, the following command line options can be used:

```bash
jupyter lab --gateway-url=http://<EG_HOST_IP>:<EG_PORT> --GatewayClient.http_user=guest --GatewayClient.http_pwd=guest-password
```

## Configuration file

If command line options are not appropriate for your environment, the Jupyter server configuration can be used to express Enterprise Gateway options. Note however, that command line options always override configuration file options:

In your `jupyter_server_config.py` file add the following for the equivalent options:

```python
c.GatewayClient.url = "http://<EG_HOST_IP>:<EG_PORT>"
c.GatewayClient.http_user = "guest"
c.GatewayClient.http_pwd = "guest-password"
```

## Docker image

All GatewayClient options have corresponding environment variable support, so if you have Jupyter Lab or Notebook already in a docker image, a corresponding docker invocation would look something like this:

```bash
docker run -t --rm \
  -e JUPYTER_GATEWAY_URL='http://<EG_HOST_IP>:<EG_PORT>' \
  -e JUPYTER_GATEWAY_HTTP_USER=guest \
  -e JUPYTER_GATEWAY_HTTP_PWD=guest-password \
  -e LOG_LEVEL=DEBUG \
  -p 8888:8888 \
  -v ${HOME}/notebooks/:/tmp/notebooks \
  -w /tmp/notebooks \
  my-image
```

Notebook files residing in `${HOME}/notebooks` can then be accessed via `http://localhost:8888`.

## Connection Timeouts

Sometimes, depending on the kind of cluster Enterprise Gateway is servicing, connection establishment and kernel startup can take a while (sometimes upwards of minutes). This is particularly true for managed clusters that perform scheduling like Hadoop YARN or Kubernetes. In these configurations it is important to configure both the connection and request timeout values.

These options are handled by the `GatewayClient.connect_timeout` (env: `JUPYTER_GATEWAY_CONNECT_TIMEOUT`) and `GatewayClient.request_timeout` (env: `JUPYTER_GATEWAY_REQUEST_TIMEOUT`) options and default to 40 seconds.

The `KERNEL_LAUNCH_TIMEOUT` environment variable will be set from these values or vice versa (whichever is greater). This value is used by EG to determine when it should give up on waiting for the kernel's startup to complete, while the other timeouts are used by Lab or Notebook when establishing the connection to EG.
