# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import tornado.web
import json
from tornado.log import access_log
from .request_utils import (parse_body, parse_args, format_request,
    headers_to_dict, parameterize_path)

from tornado import gen
from tornado.concurrent import Future
from ...mixins import TokenAuthorizationMixin, CORSMixin
from functools import partial
from .errors import UnsupportedMethodError,CodeExecutionError
import os

class NotebookAPIHandler(TokenAuthorizationMixin, CORSMixin, tornado.web.RequestHandler):
    '''Executes annotated notebook cells in response to associated HTTP requests.'''

    def initialize(self, sources, response_sources, kernel_pool, kernel_name):
        self.kernel_pool = kernel_pool
        self.sources = sources
        self.kernel_name = kernel_name
        self.response_sources = response_sources

    def on_recv(self, result_accumulator, future, parent_header, msg):
        '''
        Receives messages for a particular code execution defined by parent_header.
        Collects all outputs from the kernel until an execution state of idle is received.
        This function should be used to generate partial functions where the newly derived
        function only takes msg as an argument.

        :param result_accumulator: Accumulates results across all messages received
        :param future: A future used to set the result (errors via exceptions)
        :param parent_header: The parent header value in the messages, indicating how
            results map to requests
        :param msg: The execution content/state message received.
        '''
        if msg['parent_header']['msg_id'] == parent_header:
            # On idle status, exit our loop
            if msg['header']['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                # If the future is still running, no errors were thrown and we can set the result
                if future.running():
                    result_accumulator['content'] = ''.join(result_accumulator['content'])
                    future.set_result(result_accumulator['content'])
            # Store the execute result
            elif msg['header']['msg_type'] == 'execute_result':
                result_accumulator['content'].append(msg['content']['data'])
            # Accumulate the stream messages
            elif msg['header']['msg_type'] == 'stream':
                # Only take stream output if it is on stdout or if the kernel
                # is non-confirming and does not name the stream
                if 'name' not in msg['content'] or msg['content']['name'] == 'stdout':
                    result_accumulator['content'].append((msg['content']['text']))
            # Store the error message
            elif msg['header']['msg_type'] == 'error':
                error_name = msg['content']['ename']
                error_value = msg['content']['evalue']
                future.set_exception(CodeExecutionError(
                    'Error {}: {} \n'.format(error_name, error_value)
                ))

    def execute_code(self, kernel_client, kernel_id, source_code):
        '''Executes source_code on the kernel specified and will return a Future to indicate when code
        execution is completed. If the code execution results in an error, a CodeExecutionError is raised.
        '''
        future = Future()
        result_accumulator = {'content' : []}
        parent_header = kernel_client.execute(source_code)
        on_recv_func = partial(self.on_recv, result_accumulator, future, parent_header)
        self.kernel_pool.on_recv(kernel_id, on_recv_func)
        return future

    @gen.coroutine
    def _handle_request(self):
        '''Translates a HTTP request into code to execute on a kernel.'''
        self.response_future = Future()
        kernel_client, kernel_id = yield self.kernel_pool.acquire()
        try:
            # Method not supported
            if self.request.method not in self.sources:
                raise UnsupportedMethodError(self.request.method)

            # Set the Content-Type and status to default values
            self.set_header('Content-Type', 'text/plain')
            self.set_status(200)

            # Get the source to execute in response to this request
            source_code = self.sources[self.request.method]
            # Build the request dictionary
            request = json.dumps({
                'body' : parse_body(self.request),
                'args' : parse_args(self.request.query_arguments),
                'path' : self.path_kwargs,
                'headers' : headers_to_dict(self.request.headers)
            })
            # Turn the request string into a valid code string
            request_code = format_request(request)

            # Run the request and source code and yield until there's a result
            access_log.debug('Request code for notebook cell is: {}'.format(request_code))
            request_future = self.execute_code(kernel_client, kernel_id, request_code)
            yield request_future
            source_future = self.execute_code(kernel_client, kernel_id, source_code)
            source_result = yield source_future

            # If a response code cell exists, execute it
            if self.request.method in self.response_sources:
                response_code = self.response_sources[self.request.method]
                response_future = self.execute_code(kernel_client, kernel_id, response_code)

                # Wait for the response and parse the json value
                response_result = yield response_future
                response = json.loads(response_result)

                # Copy all the header values into the tornado response
                if 'headers' in response:
                    for header in response['headers']:
                        self.set_header(header, response['headers'][header])

                # Set the status code if it exists
                if 'status' in response:
                    self.set_status(response['status'])

            # Write the result of the source code execution
            self.write(source_result)
        # If there was a problem executing an code, return a 500
        except CodeExecutionError as err:
            self.write(err.error_message)
            self.set_status(500)
        # An unspported method was called on this handler
        except UnsupportedMethodError:
            self.set_status(405)
        finally:
            # Always make sure we release the kernel and finish the request
            self.response_future.set_result(None)
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

    def options(self, **kwargs):
        self.finish()

class NotebookDownloadHandler(TokenAuthorizationMixin, CORSMixin, tornado.web.StaticFileHandler):
    '''Allows clients to download the original notebook behind the HTTP facade.'''
    def initialize(self, path):
        self.dirname, self.filename = os.path.split(path)
        super(NotebookDownloadHandler, self).initialize(self.dirname)

    def get(self, include_body=True):
        super(NotebookDownloadHandler, self).get(self.filename, include_body)
