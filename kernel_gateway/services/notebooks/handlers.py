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
    execution_timeout = 5
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

    def _send_code(self, code, block=True):
        # execute the code and return the result and HTTP status code
        self.kernel_client.execute(code)
        result_found = False
        iopub_message = None
        result = None
        status = 200
        try:
            while(result is None):
                iopub_message = self.kernel_client.get_iopub_msg(block=block, timeout=self.execution_timeout)
                if iopub_message['header']['msg_type'] == 'execute_result':
                    result = iopub_message['content']['data']
                elif iopub_message['header']['msg_type'] == 'stream':
                    result = iopub_message['content']['text']
                elif iopub_message['header']['msg_type'] == 'error':
                    result = 'Error {}: {} \n'.format(
                        iopub_message['content']['ename'],
                        iopub_message['content']['evalue']
                    )
                    status = 500
        except Empty:
            access_log.debug('Never found execute result')
            pass

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
        self._send_code(request_code, False)
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
