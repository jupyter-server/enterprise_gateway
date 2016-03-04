# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for kernel CRUD and communication."""

import json
import tornado
import notebook.services.kernels.handlers as notebook_handlers
from ...mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from ...services.activity.manager import activity, LAST_MESSAGE_TO_CLIENT, LAST_MESSAGE_TO_KERNEL, LAST_TIME_STATE_CHANGED, BUSY, CONNECTIONS, LAST_CLIENT_CONNECT, LAST_CLIENT_DISCONNECT
from datetime import datetime

class MainKernelHandler(TokenAuthorizationMixin,
                        CORSMixin,
                        JSONErrorsMixin,
                        notebook_handlers.MainKernelHandler):
    """Extends the notebook main kernel handler with token auth, CORS, and
    JSON errors.
    """
    def post(self):
        """Overrides the super class method to honor the max number of allowed
        kernels configuration setting.

        Allows the request to reach the super class if no limit is set or if the
        maximum is not reached.

        Raises
        ------
        tonrado.web.HTTPError
            402 Payment Required (for lack of a better HTTP error code and
            mimicking what Google does) if the limit is reached
        """
        max_kernels = self.settings['kg_max_kernels']
        if max_kernels is not None:
            km = self.settings['kernel_manager']
            kernels = km.list_kernels()
            if len(kernels) >= max_kernels:
                raise tornado.web.HTTPError(402, 'Resource Limit')

        super(MainKernelHandler, self).post()

    def get(self):
        """Overrides the super class method to honor the the kernel listing
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

    def get_json_body(self):
        """Overrides the super class method to honor the configured default
        kernel name when one is not included in the JSON body of the request.

        Returns
        -------
        dict
            Model object representing information about the requested kernel
        """
        model = super(MainKernelHandler, self).get_json_body()
        if 'kg_default_kernel_name' in self.settings and self.settings['kg_default_kernel_name'] is not '':
            if model is None:
                model = {
                    'name': self.settings['kg_default_kernel_name']
                }
            else:
                model.setdefault('name', self.settings['kg_default_kernel_name'])
        return model

class KernelHandler(TokenAuthorizationMixin,
                    CORSMixin,
                    JSONErrorsMixin,
                    notebook_handlers.KernelHandler):
    """Extends the notebook kernel handler with token auth, CORS, JSON
    errors, and kernel activity tracking.
    """
    def delete(self, kernel_id):
        """Override the super class method to stop tracking activity for a
        kernel that is being deleted.


        """
        if self.settings.get('kg_list_kernels'):
            activity.remove(kernel_id)
        super(KernelHandler, self).delete(kernel_id)

class ZMQChannelsHandler(TokenAuthorizationMixin,
                         notebook_handlers.ZMQChannelsHandler):
    """Extends the notebook websocket to zmq handler with token auth and
    kernel activity tracking.
    """
    def open(self, kernel_id):
        """Overrides the super class method to track connections to a kenrel.

        Parameters
        ----------
        kernel_id : str
            Opening a connection to this kernel
        """
        if self.settings.get('kg_list_kernels'):
            activity.publish(self.kernel_id, LAST_CLIENT_CONNECT, datetime.now().isoformat())
            activity.increment_activity(self.kernel_id, CONNECTIONS)
        super(ZMQChannelsHandler, self).open(kernel_id)

    def on_close(self):
        """Overrides the super class method to track disconnections from a
        kernel.
        """
        if self.settings.get('kg_list_kernels'):
            activity.publish(self.kernel_id, LAST_CLIENT_DISCONNECT, datetime.now().isoformat())
            activity.decrement_activity(self.kernel_id, CONNECTIONS)
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
                    activity.publish(self.kernel_id, BUSY, True)
                # Else if the status is idle, set the busy to False
                elif msg_content['execution_state'] == 'idle':
                    activity.publish(self.kernel_id, BUSY, False)
                # Record the time the state was changed
                activity.publish(self.kernel_id, LAST_TIME_STATE_CHANGED, datetime.now().isoformat())

            activity.publish(self.kernel_id, LAST_MESSAGE_TO_CLIENT, datetime.now().isoformat())
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
            activity.publish(self.kernel_id, LAST_MESSAGE_TO_KERNEL, datetime.now().isoformat())
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
