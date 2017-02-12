# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel CRUD and communication."""

import json
import tornado
import notebook.services.kernels.handlers as notebook_handlers
from tornado import gen
from functools import partial
from datetime import datetime
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from ...services.activity.manager import (LAST_MESSAGE_TO_CLIENT,
    LAST_MESSAGE_TO_KERNEL, LAST_TIME_STATE_CHANGED, BUSY, CONNECTIONS,
    LAST_CLIENT_CONNECT, LAST_CLIENT_DISCONNECT)

class MainKernelHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        notebook_handlers.MainKernelHandler):
    """Extends the notebook main kernel handler with token auth, CORS, and
    JSON errors.
    """

    @property
    def env_whitelist(self):
        return self.settings['kg_personality'].env_whitelist

    @gen.coroutine
    def post(self):
        """Overrides the super class method to honor the max number of allowed
        kernels configuration setting and to support custom kernel environment
        variables for every request.

        Delegates the request to the super class implementation if no limit is
        set or if the maximum is not reached. Otherwise, responds with an error.

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if the limit is reached
        """
        max_kernels = self.settings['kg_max_kernels']
        if max_kernels is not None:
            km = self.settings['kernel_manager']
            kernels = km.list_kernels()
            if len(kernels) >= max_kernels:
                raise tornado.web.HTTPError(403, 'Resource Limit')

        # Try to get env vars from the request body
        model = self.get_json_body()
        if model is not None and 'env' in model:
            if not isinstance(model['env'], dict):
                raise tornado.web.HTTPError(400)
            # Whitelist KERNEL_* args and those allowed by configuration
            env = {key: value for key, value in model['env'].items()
                   if key.startswith('KERNEL_') or key in self.env_whitelist}
            # No way to override the call to start_kernel on the kernel manager
            # so do a temporary partial (ugh)
            orig_start = self.kernel_manager.start_kernel
            self.kernel_manager.start_kernel = partial(self.kernel_manager.start_kernel, env=env)
            try:
                yield super(MainKernelHandler, self).post()
            finally:
                self.kernel_manager.start_kernel = orig_start
        else:
            yield super(MainKernelHandler, self).post()

    def get(self):
        """Overrides the super class method to honor the kernel listing
        configuration setting.

        Allows the request to reach the super class if listing is enabled.

        Raises
        ------
        tornado.web.HTTPError
            403 Forbidden if kernel listing is disabled
        """
        if not self.settings.get('kg_list_kernels'):
            raise tornado.web.HTTPError(403, 'Forbidden')
        else:
            super(MainKernelHandler, self).get()

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()

class KernelHandler(TokenAuthorizationMixin,
                    CORSMixin,
                    JSONErrorsMixin,
                    notebook_handlers.KernelHandler):
    """Extends the notebook kernel handler with token auth, CORS, JSON
    errors, and kernel activity tracking.
    """

    @property
    def activity(self):
        return self.settings['activity_manager']

    def delete(self, kernel_id):
        """Override the super class method to stop tracking activity for a
        kernel that is being deleted.

        Parameters
        ----------
        kernel_id
            ID of the kernel to stop tracking
        """
        if self.settings.get('kg_list_kernels'):
            self.activity.remove(kernel_id)
        super(KernelHandler, self).delete(kernel_id)

    def options(self, **kwargs):
        """Method for properly handling CORS pre-flight"""
        self.finish()

class ZMQChannelsHandler(TokenAuthorizationMixin,
                         notebook_handlers.ZMQChannelsHandler):
    """Extends the notebook websocket to zmq handler with token auth and
    kernel activity tracking.
    """
    @property
    def activity(self):
        return self.settings['activity_manager']

    def open(self, kernel_id):
        """Overrides the super class method to track connections to a kenrel.

        Parameters
        ----------
        kernel_id : str
            Opening a connection to this kernel
        """
        if self.settings.get('kg_list_kernels'):
            self.activity.publish(self.kernel_id, LAST_CLIENT_CONNECT, datetime.utcnow().isoformat())
            self.activity.increment_activity(self.kernel_id, CONNECTIONS)
        super(ZMQChannelsHandler, self).open(kernel_id)

    def on_close(self):
        """Overrides the super class method to track disconnections from a
        kernel.
        """
        if self.settings.get('kg_list_kernels'):
            self.activity.publish(self.kernel_id, LAST_CLIENT_DISCONNECT, datetime.utcnow().isoformat())
            self.activity.decrement_activity(self.kernel_id, CONNECTIONS)
        super(ZMQChannelsHandler, self).on_close()

    def _on_zmq_reply(self, stream, msg_list):
        """Overrides the super class method to track communication activity
        from a kernel as well as kernel idle/busy status.

        Parameters
        ----------
        kernel_id : str
            Kernel sending the message
        """
        if self.settings.get('kg_list_kernels'):
            msg_metadata = json.loads(msg_list[3].decode('UTF-8'))
            # If the message coming back is a status message, we need to inspect it
            if msg_metadata['msg_type'] == 'status':
                msg_content = json.loads(msg_list[6].decode('UTF-8'))
                # If the status is busy, set the busy to True
                if msg_content['execution_state'] == 'busy':
                    self.activity.publish(self.kernel_id, BUSY, True)
                # Else if the status is idle, set the busy to False
                elif msg_content['execution_state'] == 'idle':
                    self.activity.publish(self.kernel_id, BUSY, False)
                # Record the time the state was changed
                self.activity.publish(self.kernel_id, LAST_TIME_STATE_CHANGED, datetime.utcnow().isoformat())

            self.activity.publish(self.kernel_id, LAST_MESSAGE_TO_CLIENT, datetime.utcnow().isoformat())
        super(ZMQChannelsHandler, self)._on_zmq_reply(stream, msg_list)

    def on_message(self, msg):
        """Overrides the super class method to track communication activity
        to a kernel.

        Parameters
        ----------
        msg : str
            Message sent to a kernel
        """
        if self.settings.get('kg_list_kernels'):
            self.activity.publish(self.kernel_id, LAST_MESSAGE_TO_KERNEL, datetime.utcnow().isoformat())
        super(ZMQChannelsHandler, self).on_message(msg)

default_handlers = []
for path, cls in notebook_handlers.default_handlers:
    if cls.__name__ in globals():
        # Use the same named class from here if it exists
        default_handlers.append((path, globals()[cls.__name__]))
    else:
        # Gen a new type with CORS and token auth
        bases = (TokenAuthorizationMixin, CORSMixin, cls)
        default_handlers.append((path, type(cls.__name__, bases, {})))
