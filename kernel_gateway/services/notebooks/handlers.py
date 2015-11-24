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
    get_source = None
    put_source = None
    post_source = None
    delete_source = None
    kernel_client = None
    execution_timeout = 5
    kernel_name = ''
    
    def initialize(self, sources, kernel_client, kernel_name):
        self.kernel_client = kernel_client
        if 'GET' in sources:
            self.get_source = sources['GET']
        if 'POST' in sources:
            self.post_source = sources['POST']
        if 'PUT' in sources:
            self.put_source = sources['PUT']
        if 'DELETE' in sources:
            self.delete_source = sources['DELETE']
        self.kernel_name = kernel_name

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

    def _handle_request(self, source_code):
        if source_code is None:
            self.set_status(405)
            self.finish()
            return

        REQUEST = json.dumps({
            'body' : parse_body(self.request.body),
            'args' : parse_args(self.request.arguments),
            'path' : self.path_kwargs
        })
        if self.kernel_name == 'r':
            request_code = "REQUEST <- '"  + REQUEST + "'"
        else:
            request_code = "REQUEST = '"  + REQUEST + "'"

        access_log.debug('Request code for notebook cell is: {}'.format(request_code))
        # TODO: Need to figure out multil-lang assignment
        self._send_code(request_code, False)
        result, status = self._send_code(source_code)

        # TODO: Will we need to add the ability to specify mime types?
        self.set_header('Content-Type', 'text/plain')
        if result is not None:
            self.write(result)
        self.set_status(status)
        self.finish()

    def get(self, **kwargs):
        # execute the get_source
        self._handle_request(self.get_source)
    def post(self, **kwargs):
        # execute the post_source
        self._handle_request(self.post_source)

    def put(self, **kwargs):
        # execute the put_source
        print('in put method')
        self._handle_request(self.put_source)

    def delete(self, **kwargs):
        print('in delete method')
        # execute the delete_source
        self._handle_request(self.delete_source)
