# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tornado handlers for invoking notebook cells as web APIs."""

import os
import json
import tornado.web
from tornado.log import access_log
from .request_utils import (parse_body, parse_args, format_request,
    headers_to_dict, parameterize_path)
from tornado import gen
from tornado.concurrent import Future
from ..mixins import TokenAuthorizationMixin, CORSMixin, JSONErrorsMixin
from functools import partial
from .errors import UnsupportedMethodError, CodeExecutionError

class NotebookAPIHandler(TokenAuthorizationMixin,
                         CORSMixin,
                         JSONErrorsMixin,
                         tornado.web.RequestHandler):
    """Executes code from a notebook cell in response to HTTP requests at the
    route registered in association with this class.

    Supports the GET, POST, PUT, and DELETE HTTP methods.

    Parameters
    ----------
    sources : dict
        Maps HTTP verb strings to annotated cells extracted from a notebook
    response_sources
        Maps HTTP verb strings to ResponseInfo annotated cells extracted from a
        notebook
    kernel_pool
        Instance of services.kernels.ManagedKernelPool
    kernel_name
        Kernel spec name used to launch the kernel pool. Identifies the
        language of the source code cells.

    Attributes
    ----------
    See parameters: they are stored as passed as instance variables.

    See Also
    --------
    services.cell.parser.APICellParser for detail about how the source cells
    are identified, parsed, and associated with HTTP verbs and paths.
    """
    def initialize(self, sources, response_sources, kernel_pool, kernel_name):
        self.kernel_pool = kernel_pool
        self.sources = sources
        self.kernel_name = kernel_name
        self.response_sources = response_sources

    def finish_future(self, future, result_accumulator):
        """Resolves the promise to respond to a HTTP request handled by a
        kernel in the pool.

        Defines precedence for the kind of response:

        1. If any error occurred, resolve with a CodeExecutionError exception
        2. If any stream message was collected from the kernel, resolve with
            the joined string of stream messages
        3. If an execute_result was collected, resolve with that result object
            JSON encoded
        4. Resolve with an empty string

        Parameters
        ----------
        future : tornado.concurrent.Future
            Promise of a future response to an API request
        result_accumulator : dict
            Dictionary of results from a kernel with at least the keys error,
            stream, and result
        """
        if result_accumulator['error']:
            future.set_exception(CodeExecutionError(result_accumulator['error']))
        elif len(result_accumulator['stream']) > 0:
            future.set_result(''.join(result_accumulator['stream']))
        elif result_accumulator['result']:
            future.set_result(json.dumps(result_accumulator['result']))
        else:
            # If nothing was set, return an empty value
            future.set_result('')

    def on_recv(self, result_accumulator, future, parent_header, msg):
        """Collects ipoub messages associated with code execution request
        identified by `parent_header`.

        Continues collecting until an execution state of idle is reached.
        The first three parameters are typically applied in a partial.

        Parameters
        ----------
        result_accumulator : dict
            Accumulates data from `execute_result`, `stream` and `error`
            messages under keys `result`, `stream`, and `error` respectively
            across multiple invocations of this callback.
        future : tornado.concurrent.Future
            Promise to resolve when the kernel goes idle
        parent_header : dict
            Parent header from an `execute` request, used to identify messages
            that relate to its execution vs other executions
        msg : dict
            Kernel message received from the iopub channel
        """
        if msg['parent_header']['msg_id'] == parent_header:
            # On idle status, exit our loop
            if msg['header']['msg_type'] == 'status' and msg['content']['execution_state'] == 'idle':
                self.finish_future(future, result_accumulator)
            # Store the execute result
            elif msg['header']['msg_type'] == 'execute_result':
                result_accumulator['result'] = msg['content']['data']
            # Accumulate the stream messages
            elif msg['header']['msg_type'] == 'stream':
                # Only take stream output if it is on stdout or if the kernel
                # is non-confirming and does not name the stream
                if 'name' not in msg['content'] or msg['content']['name'] == 'stdout':
                    result_accumulator['stream'].append((msg['content']['text']))
            # Store the error message
            elif msg['header']['msg_type'] == 'error':
                error_name = msg['content']['ename']
                error_value = msg['content']['evalue']
                result_accumulator['error'] = 'Error {}: {} \n'.format(error_name, error_value)

    def execute_code(self, kernel_client, kernel_id, source_code):
        """Executes `source_code` on the kernel specified.

        Registers a callback for iopub messages. Promises to return the output
        of the execution in the future after the kernel returns to its idle
        state.

        Parameters
        ----------
        kernel_client : object
            Client to use to execute the code
        kernel_id : str
            ID of the kernel from the pool that will execute the request
        source_code : str
            Source code to execut

        Returns
        -------
        tornado.concurrent.Future
            Promise of execution result

        Raises
        ------
        CodeExecutionError
            If the kernel returns any error
        """
        future = Future()
        result_accumulator = {'stream' : [], 'error' : None, 'result' : None}
        parent_header = kernel_client.execute(source_code)
        on_recv_func = partial(self.on_recv, result_accumulator, future, parent_header)
        self.kernel_pool.on_recv(kernel_id, on_recv_func)
        return future

    @gen.coroutine
    def _handle_request(self):
        """Turns an HTTP request into annotated notebook code to execute on a
        kernel.

        Sets the HTTP response code, headers, and response body based on the
        result of the kernel execution. Then finishes the Tornado response.
        """
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
            yield self.execute_code(kernel_client, kernel_id, request_code)
            source_result = yield self.execute_code(kernel_client, kernel_id, source_code)

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
            if source_result:
                self.write(source_result)
        # If there was a problem executing an code, return a 500
        except CodeExecutionError as err:
            self.write(str(err))
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

class NotebookDownloadHandler(TokenAuthorizationMixin,
                              CORSMixin,
                              JSONErrorsMixin,
                              tornado.web.StaticFileHandler):
    """Handles requests to download the annotated notebook behind the web API.
    """
    def initialize(self, path):
        self.dirname, self.filename = os.path.split(path)
        super(NotebookDownloadHandler, self).initialize(self.dirname)

    def get(self, include_body=True):
        super(NotebookDownloadHandler, self).get(self.filename, include_body)
