# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import tornado.web
from tornado.log import access_log
import json
from .request_utils import *
try:
    from queue import Empty
except ImportError:
    from Queue import Empty

class NotebookAPIHandler(tornado.web.RequestHandler):
    kernel_client = None
    sources = None
    execution_timeout = 60
    kernel_name = ''
    _assignment_statements = {'r': "REQUEST <- '{}'",
        None : "REQUEST = '{}'"}

    def initialize(self, sources, kernel_client, kernel_name):
        self.kernel_client = kernel_client
        self.sources = sources
        self.kernel_name = kernel_name

    def _request_assignment_for_lang(self, kernel_name, expression):
        try:
            statement = self._assignment_statements[kernel_name]
        except KeyError:
            statement = self._assignment_statements[None]
        return statement.format(expression)

    def _process_messages(self, parent_header):
        idle = False
        execute_result = None
        stream_messages = []
        error_message = None
        while(not idle):
            iopub_message = self.kernel_client.get_iopub_msg(block=True, timeout=self.execution_timeout)
            # Only look at messages which are derived from the parent_header
            if iopub_message['parent_header']['msg_id'] == parent_header:
                # On idle status, exit our loop
                if iopub_message['header']['msg_type'] == 'status' and iopub_message['content']['execution_state'] == 'idle':
                    idle = True
                # Store the execute result
                elif iopub_message['header']['msg_type'] == 'execute_result':
                    execute_result = iopub_message['content']['data']
                # Accumulate the stream messages
                elif iopub_message['header']['msg_type'] == 'stream':
                    stream_messages.append(iopub_message['content']['text'])
                # Store the error message
                elif iopub_message['header']['msg_type'] == 'error':
                    error_message = 'Error {}: {} \n'.format(
                        iopub_message['content']['ename'],
                        iopub_message['content']['evalue']
                    )

        if error_message is not None:
            return True, error_message
        elif execute_result is not None and execute_result is not '':
            return False, execute_result
        else:
            return False, ''.join(stream_messages)

    def _send_code(self, code):
        # execute the code and return the result and HTTP status code
        parent_header = self.kernel_client.execute(code)
        status = 200
        error, result = self._process_messages(parent_header=parent_header)

        if error:
            status = 500

        return result, status

    def _handle_request(self):
        if self.request.method not in self.sources:
            self.set_status(405)
            self.finish()
            return

        source_code = self.sources[self.request.method]
        REQUEST = json.dumps({
            'body' : parse_body(self.request.body),
            'args' : parse_args(self.request.arguments),
            'path' : self.path_kwargs
        })
        request_code = self._request_assignment_for_lang(self.kernel_name, REQUEST)

        access_log.debug('Request code for notebook cell is: {}'.format(request_code))
        self._send_code(request_code)
        result, status = self._send_code(source_code)

        # TODO: Will we need to add the ability to specify mime types?
        self.set_header('Content-Type', 'text/plain')
        if result is not None:
            self.write(result)
        self.set_status(status)
        self.finish()

    def get(self, **kwargs):
        self._handle_request()

    def post(self, **kwargs):
        self._handle_request()

    def put(self, **kwargs):
        self._handle_request()

    def delete(self, **kwargs):
        self._handle_request()
