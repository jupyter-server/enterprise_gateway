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

from tornado import gen
from tornado.concurrent import Future

class NotebookAPIHandler(tornado.web.RequestHandler):
    kernel_pool = None
    sources = None
    kernel_name = ''
    execute_result = None
    stream_messages = []
    error_message = None
    _assignment_statements = {'r': "REQUEST <- '{}'",
        None : "REQUEST = '{}'"}

    def initialize(self, sources, kernel_pool, kernel_name):
        self.kernel_pool = kernel_pool
        self.sources = sources
        self.kernel_name = kernel_name

    def _request_assignment_for_lang(self, kernel_name, expression):
        try:
            statement = self._assignment_statements[kernel_name]
        except KeyError:
            statement = self._assignment_statements[None]
        return statement.format(expression)

    def on_recv(self, msg):
        '''
        Receives messages for a particular code execution defined by self.parent_header.
        Collects all outputs from the kernel until an execution state of idle is received.
        :param msg: The execution content/state message received.
        '''
        # Only look at messages which are derived from the parent_header
        # TODO Refactor this so we only look for parent headers for the actual cell execution
        if msg['parent_header']['msg_id'] == self.parent_header:
            # On idle status, exit our loop
            if msg['header']['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                result = {'status': 200, 'content': ''}
                if self.error_message:
                    result['content'] =self.error_message
                    result['status'] = 500
                elif self.execute_result and self.execute_result is not '':
                    result['content'] = self.error_message
                else:
                    result['content'] = ''.join(self.stream_messages)
                self.execution_future.set_result(result)
            # Store the execute result
            elif msg['header']['msg_type'] == 'execute_result':
                self.execute_result = msg['content']['data']
            # Accumulate the stream messages
            elif msg['header']['msg_type'] == 'stream':
                self.stream_messages.append(msg['content']['text'])
            # Store the error message
            elif msg['header']['msg_type'] == 'error':
                self.error_message = 'Error {}: {} \n'.format(
                    msg['content']['ename'],
                    msg['content']['evalue']
                )

    @gen.coroutine
    def _handle_request(self):
        self.execute_result = None
        self.stream_messages = []
        self.error_message = None
        if self.request.method not in self.sources:
            self.set_status(405)
            self.finish()
            return

        self.execution_future = Future()
        self.response_future = Future()
        kernel_client, kernel_id = yield self.kernel_pool.acquire()
        try:
            self.kernel_pool.on_recv(kernel_id, self.on_recv)
            source_code = self.sources[self.request.method]
            REQUEST = json.dumps({
                'body' : parse_body(self.request.body),
                'args' : parse_args(self.request.arguments),
                'path' : self.path_kwargs
            })
            request_code = self._request_assignment_for_lang(self.kernel_name, REQUEST)

            access_log.debug('Request code for notebook cell is: {}'.format(request_code))
            kernel_client.execute(request_code)
            self.parent_header = kernel_client.execute(source_code)
            result = yield self.execution_future
            # TODO: Will we need to add the ability to specify mime types?
            self.set_header('Content-Type', 'text/plain')
            self.set_status(result['status'])
            self.write(result['content'])
        finally:
            self.kernel_pool.release(kernel_id)
            self.finish()


    @gen.coroutine
    def get(self, **kwargs):
        self._handle_request()
        yield self.response_future

    @gen.coroutine
    def post(self, **kwargs):
        self._handle_request()
        yield self.response_future

    @gen.coroutine
    def put(self, **kwargs):
        self._handle_request()
        yield self.response_future

    @gen.coroutine
    def delete(self, **kwargs):
        self._handle_request()
        yield self.response_future
