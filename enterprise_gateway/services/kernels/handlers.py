# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel CRUD and communication."""
from datetime import datetime, timezone
import json
import os
from functools import partial

import jupyter_server.services.kernels.handlers as jupyter_server_handlers
import tornado
from jupyter_client.jsonutil import date_default
from jupyter_server.base.handlers import APIHandler
from tornado import web
try:
    from jupyter_client.jsonutil import json_default
except ImportError:
    from jupyter_client.jsonutil import date_default as json_default

from ...mixins import CORSMixin, JSONErrorsMixin, TokenAuthorizationMixin


class MainKernelHandler(
    TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, jupyter_server_handlers.MainKernelHandler
):
    """Extends the jupyter_server main kernel handler with token auth, CORS, and
    JSON errors.
    """

    @property
    def env_whitelist(self):
        return self.settings["eg_env_whitelist"]

    @property
    def env_process_whitelist(self):
        return self.settings["eg_env_process_whitelist"]

    async def post(self):
        """Overrides the super class method to manage env in the request body.

        Max kernel limits are now enforced in RemoteMappingKernelManager.start_kernel().

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if either max kernel limit is reached (total or per user, if configured)
        """
        max_kernels = self.settings["eg_max_kernels"]
        if max_kernels is not None:
            km = self.settings["kernel_manager"]
            kernels = km.list_kernels()
            if len(kernels) >= max_kernels:
                raise tornado.web.HTTPError(403, "Resource Limit")

        # Try to get env vars from the request body
        model = self.get_json_body()
        if model is not None and "env" in model:
            if not isinstance(model["env"], dict):
                raise tornado.web.HTTPError(400)
            # Start with the PATH from the current env. Do not provide the entire environment
            # which might contain server secrets that should not be passed to kernels.
            env = {"PATH": os.getenv("PATH", "")}
            # Whitelist environment variables from current process environment
            env.update(
                {
                    key: value
                    for key, value in os.environ.items()
                    if key in self.env_process_whitelist
                }
            )
            # Whitelist KERNEL_* args and those allowed by configuration from client.  If all
            # envs are requested, just use the keys from the payload.
            env_whitelist = self.env_whitelist
            if env_whitelist == ["*"]:
                env_whitelist = model["env"].keys()
            env.update(
                {
                    key: value
                    for key, value in model["env"].items()
                    if key.startswith("KERNEL_") or key in env_whitelist
                }
            )

            # If kernel_headers are configured, fetch each of those and include in start request
            kernel_headers = {}
            missing_headers = []
            kernel_header_names = self.settings["eg_kernel_headers"]
            for name in kernel_header_names:
                if name:  # Ignore things like empty strings
                    value = self.request.headers.get(name)
                    if value:
                        kernel_headers[name] = value
                    else:
                        missing_headers.append(name)

            if len(missing_headers):
                self.log.warning(
                    "The following headers specified in 'kernel-headers' were not found: {}".format(
                        missing_headers
                    )
                )

            # No way to override the call to start_kernel on the kernel manager
            # so do a temporary partial (ugh)
            orig_start = self.kernel_manager.start_kernel
            self.kernel_manager.start_kernel = partial(
                self.kernel_manager.start_kernel, env=env, kernel_headers=kernel_headers
            )
            try:
                await super().post()
            finally:
                self.kernel_manager.start_kernel = orig_start
        else:
            await super().post()

    async def get(self):
        """Overrides the super class method to honor the kernel listing
        configuration setting.

        Allows the request to reach the super class if listing is enabled.

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if kernel listing is disabled
        """
        if not self.settings.get("eg_list_kernels"):
            raise tornado.web.HTTPError(403, "Forbidden")
        else:
            await super().get()

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()


class KernelHandler(
    TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, jupyter_server_handlers.KernelHandler
):
    """Extends the jupyter_server kernel handler with token auth, CORS, and
    JSON errors.
    """

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()

    @web.authenticated
    def get(self, kernel_id):
        km = self.kernel_manager
        km.check_kernel_id(kernel_id)
        model = km.kernel_model(kernel_id)
        self.finish(json.dumps(model, default=date_default))


class ConfigureMagicHandler(CORSMixin, JSONErrorsMixin, APIHandler):
    @web.authenticated
    async def post(self, kernel_id):
        self.log.info(f"Update request received for kernel: {kernel_id}")
        km = self.kernel_manager
        km.check_kernel_id(kernel_id)
        payload = self.get_json_body()
        self.log.debug(f"Request payload: {payload}")
        if payload is None:
            self.log.info("Empty payload in the request body.")
            self.finish(json.dumps({"message": "Empty payload received. No operation performed on the Kernel."},
                                   default=date_default))
            return
        if type(payload) != dict:
            self.log.info("Payload is not in acceptable format.")
            raise web.HTTPError(400, u'Invalid JSON payload received.')
        if payload.get("env", None) is None:  # We only allow env field for now.
            self.log.info("Payload is missing the required env field.")
            raise web.HTTPError(400, u'Missing required field `env` in payload.')
        kernel = km.get_kernel(kernel_id)
        if kernel.restarting:  # handle duplicate request.
            self.log.info("An existing restart request is still in progress. Skipping this request.")
            raise web.HTTPError(400, u'Duplicate Kernel update request received for Id: %s.' % kernel_id)
        try:
            # update Kernel metadata
            kernel.set_user_extra_overrides(payload)
            await km.restart_kernel(kernel_id)
            kernel.fire_kernel_event_callbacks(event="kernel_refresh", zmq_messages=payload.get("zmq_messages", {}))
        except web.HTTPError as he:
            self.log.exception(f"HTTPError exception occurred in refreshing kernel: {kernel_id}: {he}")
            await km.shutdown_kernel(kernel_id)
            kernel.fire_kernel_event_callbacks(event="kernel_refresh_failure", zmq_messages=payload.get("zmq_messages", {}))
            raise he
        except Exception as e:
            self.log.exception(f"An exception occurred in updating kernel : {kernel_id}: {e}")
            await km.shutdown_kernel(kernel_id)
            kernel.fire_kernel_event_callbacks(event="kernel_refresh_failure", zmq_messages=payload.get("zmq_messages", {}))
            raise web.HTTPError(500, u'Error occurred while refreshing Kernel: %s.' % kernel_id, reason="{}".format(e))
        else:
            response_body = {
                "message": f"Successfully refreshed kernel with id: {kernel_id}"
            }
            self.finish(json.dumps(response_body, default=date_default))
            return


class RemoteZMQChannelsHandler(TokenAuthorizationMixin,
                               CORSMixin,
                               JSONErrorsMixin,
                               jupyter_server_handlers.ZMQChannelsHandler):

    def open(self, kernel_id):
        self.log.info(f"Websocket open request received for kernel: {kernel_id}")
        super(RemoteZMQChannelsHandler, self).open(kernel_id)
        km = self.kernel_manager
        km.add_kernel_event_callbacks(kernel_id, self.on_kernel_refresh, "kernel_refresh")
        km.add_kernel_event_callbacks(kernel_id, self.on_kernel_refresh_failure, "kernel_refresh_failure")

    def on_kernel_refresh(self, **kwargs):
        self.log.info("Refreshing the client websocket to kernel connection.")
        self.refresh_zmq_sockets()
        zmq_messages = kwargs.get("zmq_messages", {})
        if "stream_reply" in zmq_messages:
            self.log.debug("Sending stream_reply success message.")
            success_message = zmq_messages.get("stream_reply")
            success_message["content"] = {
                "name": "stdout",
                'text': "The Kernel is successfully refreshed."
            }
            self._send_ws_message(success_message)
        if "exec_reply" in zmq_messages:
            self.log.debug("Sending exec_reply message.")
            self._send_ws_message(zmq_messages.get("exec_reply"))
        if "idle_reply" in zmq_messages:
            self.log.debug("Sending idle_reply message.")
            self._send_ws_message(zmq_messages.get("idle_reply"))
        self._send_status_message('kernel_refreshed')  # In the future, UI clients might start to consume this.

    def on_kernel_refresh_failure(self, **kwargs):
        self.log.error("Kernel %s refresh failed!", self.kernel_id)
        zmq_messages = kwargs.get("zmq_messages", {})
        if "error_reply" in zmq_messages:
            self.log.debug("Sending stream_reply error message.")
            error_message = zmq_messages.get("error_reply")
            error_message["content"] = {
                "ename": "KernelRefreshFailed",
                'evalue': "The Kernel refresh operation failed.",
                'traceback': ["The Kernel refresh operation failed."]
            }
            self._send_ws_message(error_message)
        if "exec_reply" in zmq_messages:
            self.log.debug("Sending exec_reply message.")
            exec_reply = zmq_messages.get("exec_reply").copy()
            if "metadata" in exec_reply:
                exec_reply["metadata"]["status"] = "error"
            exec_reply["content"]["status"] = "error"
            exec_reply["content"]["ename"] = "KernelRefreshFailed."
            exec_reply["content"]["evalue"] = "The Kernel refresh operation failed."
            exec_reply["content"]["traceback"] = ["The Kernel refresh operation failed."]
            self._send_ws_message(exec_reply)
        if "idle_reply" in zmq_messages:
            self.log.info("Sending idle reply message.")
            self._send_ws_message(zmq_messages.get("idle_reply"))
        self.log.debug("sending kernel dead message.")
        self._send_status_message('dead')

    def refresh_zmq_sockets(self):
        self.close_existing_streams()
        kernel = self.kernel_manager.get_kernel(self.kernel_id)
        self.session.key = kernel.session.key  # refresh the session key
        self.log.debug("Creating new ZMQ Socket streams.")
        self.create_stream()
        for channel, stream in self.channels.items():
            self.log.debug(f"Updating channel: {channel}")
            stream.on_recv_stream(self._on_zmq_reply)

    def close_existing_streams(self):
        self.log.debug(f"Closing existing channels for kernel: {self.kernel_id}")
        for channel, stream in self.channels.items():
            if stream is not None and not stream.closed():
                self.log.debug(f"Close channel : {channel}")
                stream.on_recv(None)
                stream.close()
        self.channels = {}

    def _send_ws_message(self, kernel_msg):
        self.log.debug(f"Sending websocket message: {kernel_msg}")
        if "header" in kernel_msg and type(kernel_msg["header"] == dict):
            kernel_msg["header"]["date"] = datetime.utcnow().replace(tzinfo=timezone.utc)
        self.write_message(json.dumps(kernel_msg, default=json_default))

    def on_close(self):
        self.log.info(f"Websocket close request received for kernel: {self.kernel_id}")
        super(RemoteZMQChannelsHandler, self).on_close()
        self.kernel_manager.remove_kernel_event_callbacks(self.kernel_id, self.on_kernel_refresh, "kernel_refresh")
        self.kernel_manager.remove_kernel_event_callbacks(self.kernel_id, self.on_kernel_refresh_failure,
                                                          "kernel_refresh_failure")


_kernel_id_regex = r"(?P<kernel_id>\w+-\w+-\w+-\w+-\w+)"
default_handlers = [
    (r"/api/configure/%s" % _kernel_id_regex, ConfigureMagicHandler)
]
for path, cls in jupyter_server_handlers.default_handlers:
    if cls.__name__ in globals():
        # Use the same named class from here if it exists
        default_handlers.append((path, globals()[cls.__name__]))
    elif cls.__name__ == jupyter_server_handlers.ZMQChannelsHandler.__name__:  # TODO: check for override.
        default_handlers.append((path, RemoteZMQChannelsHandler))
    else:
        # Gen a new type with CORS and token auth
        bases = (TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin, cls)
        default_handlers.append((path, type(cls.__name__, bases, {})))
