# Kernel Session Persistence

Enabling kernel session persistence allows Jupyter Notebooks to reconnect to kernels when Enterprise Gateway is restarted. There are two ways of persisting kernel sessions: _File Kernel Session Persistence_ and _Webhook Kernel Session Persistence_.

NOTE: Kernel Session Persistence should be considered experimental!

## File Kernel Session Persistence

File Kernel Session Persistence stores all kernel sessions as a file in a specified directory. To enable this, set the environment variable `EG_KERNEL_SESSION_PERSISTENCE=True` or configure `FileKernelSessionManager.enable_persistence=True`. To change the directory in which the kernel session file is being saved, either set the environment variable `EG_PERSISTENCE_ROOT` or configure `FileKernelSessionManager.persistence_root` to the directory.

## Webhook Kernel Session Persistence

Webhook Kernel Session Persistence stores all kernel sessions to any database. In order for this to work, an API must be created. The API must include four endpoints:

- A GET that will retrieve a list of all kernel sessions from a database
- A GET that will take the kernel id as a path variable and retrieve that information from a database
- A DELETE that will delete all kernel sessions, where the body of the request is a list of kernel ids
- A POST that will take kernel id as a path variable and kernel session in the body of the request and save it to a database where the object being saved is:

```
    {
      kernel_id: KERNEL ID,
      kernel: KERNEL SESSION OBJECT
    }
```

To enable the webhook kernel session persistence, set the environment variable `EG_KERNEL_SESSION_PERSISTENCE=True` or configure `WebhookKernelSessionManager.enable_persistence=True`. To connect the API, set the environment varible `EG_WEBHOOK_URL` or configure `WebhookKernelSessionManager.webhook_url` to the API endpoint.

### Enabling Authentication

Enabling authentication is an option if the API requries it for requests. Set the environment variable `EG_AUTH_TYPE` or configure `WebhookKernelSessionManager.auth_type` to be either `Basic` or `Digest`. If it is set to an empty string authentication won't be enabled.

Then set the environment variables `EG_WEBHOOK_USERNAME` and `EG_WEBHOOK_PASSWORD` or configure `WebhookKernelSessionManager.webhook_username` and `WebhookKernelSessionManager.webhook_password` to provide the username and password for authentication.

## Testing Kernel Session Persistence

Once kernel session persistence has been enabled and configured, create a kernel by opening up a Jupyter Notebook. Save some variable in that notebook and shutdown Enterprise Gateway using `kill -9 PID`, wher `PID` is the PID of gateway. Restart Enterprise Gateway and refresh you notebook tab. If all worked correctly, the variable should be loaded without the need to rerun the cell.

If you are using docker, ensure the container isn't tied to the PID of Enterprise Gateway. The container should still run after killing that PID.
