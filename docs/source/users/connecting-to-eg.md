# Connecting JupyterLab or Jupyter Notebook to Enterprise Gateway

To leverage the benefits of Enterprise Gateway, it's helpful to redirect a Jupyter server's kernel management to the Gateway server. This allows better separation of the user's notebooks from the managed computer cluster (Kubernetes, Hadoop YARN, Docker Swarm, etc.) on which Enterprise Gateway resides. A Jupyter server can be configured to relay kernel requests to an Enterprise Gateway server in several ways.

## Command line

To instruct the server to connect to an Enterprise Gateway instance running on host `<EG_HOST_IP>` on port `<EG_PORT>`, the following command line options can be used:

```bash
jupyter lab --gateway-url=http://<EG_HOST_IP>:<EG_PORT>
```

**With HTTP Basic authentication**

```bash
jupyter lab --gateway-url=http://<EG_HOST_IP>:<EG_PORT> --GatewayClient.http_user=<username> --GatewayClient.http_pwd=<password>
```

```{admonition} These are the *client's* credentials, not a Gateway account
:class: important
`<username>` and `<password>` are the HTTP Basic Auth credentials that **the Jupyter
Server hosting your JupyterLab/Notebook sends to** Enterprise Gateway on each request.
They are **not** a built-in Gateway account, and there are no default login credentials — both
options default to `None` (no `Authorization` header is sent). A stock Enterprise
Gateway server does **not** validate these values; whether they are enforced is an
*operator* decision. See [Authenticating to Enterprise Gateway](#authenticating-to-enterprise-gateway)
below and [Configuring security](../operators/config-security.md).
```

## Configuration file

If command line options are not appropriate for your environment, the Jupyter server configuration can be used to express Enterprise Gateway options. Note however, that command line options always override configuration file options:

In your `jupyter_server_config.py` file add the following for the equivalent options:

```python
c.GatewayClient.url = "http://<EG_HOST_IP>:<EG_PORT>"
c.GatewayClient.http_user = "<username>"
c.GatewayClient.http_pwd = "<password>"
```

## Docker image

All GatewayClient options have corresponding environment variable support, so if you have Jupyter Lab or Notebook already in a docker image, a corresponding docker invocation would look something like this:

```bash
docker run -t --rm \
  -e JUPYTER_GATEWAY_URL='http://<EG_HOST_IP>:<EG_PORT>' \
  -e JUPYTER_GATEWAY_HTTP_USER=<username> \
  -e JUPYTER_GATEWAY_HTTP_PWD=<password> \
  -e LOG_LEVEL=DEBUG \
  -p 8888:8888 \
  -v ${HOME}/notebooks/:/tmp/notebooks \
  -w /tmp/notebooks \
  my-image
```

Notebook files residing in `${HOME}/notebooks` can then be accessed via `http://localhost:8888`.

## Authenticating to Enterprise Gateway

A common point of confusion is _which side_ owns the credentials shown above.
Enterprise Gateway itself performs **no user authentication by default** — it assumes
requests have already been authenticated upstream (for example, by
[Apache Knox](https://knox.apache.org/) or
[JupyterHub](https://jupyterhub.readthedocs.io/en/latest/)). The `GatewayClient`
options simply control what credentials the Jupyter server _presents_ on each request;
whether those credentials are enforced is entirely an operator decision.

The diagram below shows where each option applies:

```{mermaid}
flowchart LR
    subgraph client["Jupyter Server (client)"]
        lab["JupyterLab / Notebook<br/>(frontend)"]
        GC["GatewayClient<br/>http_user / http_pwd<br/>auth_token / auth_scheme"]
    end
    subgraph proxy["Optional proxy"]
        P["Validates<br/>Basic Auth"]
    end
    subgraph eg["Enterprise Gateway (server)"]
        subgraph server["Jupyter Server (server)"]
            T["EG_AUTH_TOKEN gate"]
            K["Kernel launch<br/>KERNEL_USERNAME → authorization"]
        end
    end
    lab --> GC
    GC -- "Authorization header" --> P
    P --> T
    T --> K
```

The Gateway client can attach the following to each request:

- **HTTP Basic Auth** — `http_user` / `http_pwd` (env: `JUPYTER_GATEWAY_HTTP_USER` /
  `JUPYTER_GATEWAY_HTTP_PWD`). Both default to `None`. Enterprise Gateway does **not**
  validate these itself; they are only meaningful when a proxy in front of the Gateway
  (such as Knox) checks them. There is no built-in `guest` / `guest-password` account.
- **Bearer / token auth** — `auth_token` and optional `auth_scheme` (env:
  `JUPYTER_GATEWAY_AUTH_TOKEN` / `JUPYTER_GATEWAY_AUTH_SCHEME`) send an
  `Authorization: {auth_scheme} {auth_token}` header. To have the Gateway server
  _enforce_ a token, the operator sets `EG_AUTH_TOKEN` (or
  `c.EnterpriseGatewayApp.auth_token`) on the server; requests then require a matching
  `Authorization: token <value>` header (or `?token=<value>`) and are rejected with
  HTTP 401 otherwise.
- **KERNEL_USERNAME** — conveys the already-authenticated user's identity for
  _authorization_ (allowed/blocked users) and _impersonation_ at kernel launch. This is
  an identity, not a secret.

```{seealso}
Operators configuring what the Gateway server actually enforces should refer to
[Configuring security](../operators/config-security.md), which covers `EG_AUTH_TOKEN`,
`KERNEL_USERNAME`-based authorization, impersonation, and SSL/TLS.
```

## Connection Timeouts

Sometimes, depending on the kind of cluster Enterprise Gateway is servicing, connection establishment and kernel startup can take a while (sometimes upwards of minutes). This is particularly true for managed clusters that perform scheduling like Hadoop YARN or Kubernetes. In these configurations it is important to configure both the connection and request timeout values.

These options are handled by the `GatewayClient.connect_timeout` (env: `JUPYTER_GATEWAY_CONNECT_TIMEOUT`) and `GatewayClient.request_timeout` (env: `JUPYTER_GATEWAY_REQUEST_TIMEOUT`) options and default to 40 seconds.

The `KERNEL_LAUNCH_TIMEOUT` environment variable will be set from these values or vice versa (whichever is greater). This value is used by EG to determine when it should give up on waiting for the kernel's startup to complete, while the other timeouts are used by Lab or Notebook when establishing the connection to EG.
