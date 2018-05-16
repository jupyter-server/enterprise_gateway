
import os
import requests

from uuid import uuid4
from pprint import pprint
from tornado.escape import json_encode, json_decode, utf8
from threading import Thread
import websocket

try:  # prefer python 3, fallback to 2
    import queue as queue
except ImportError:
    import Queue as queue

DEFAULT_TIMEOUT = 60 * 60

class KernelLauncher:
    DEFAULT_USERNAME = os.getenv('KERNEL_USERNAME', 'bob')
    DEFAULT_GATEWAY_HOST = os.getenv('GATEWAY_HOST', 'localhost:8888')

    def __init__(self, host=DEFAULT_GATEWAY_HOST):
        self.http_api_endpoint = 'http://{}/api/kernels'.format(host)
        self.ws_api_endpoint = 'ws://{}/api/kernels'.format(host)
        self.kernel = None

    def launch(self, kernelspec_name, username=DEFAULT_USERNAME, timeout=DEFAULT_TIMEOUT):
        print('Launching a {} kernel ....'.format(kernelspec_name))

        json_data = {'name': kernelspec_name}
        if username is not None:
            json_data['env'] = {'KERNEL_USERNAME': username}

        response = requests.post(self.http_api_endpoint, data=json_encode(json_data))
        if response.status_code == 201:
            json_data = response.json()
            kernel_id = json_data.get("id")
            print('Launched kernel with id {}'.format(kernel_id))
        else:
            raise RuntimeError('Error creating kernel : {} response code \n {}'.
                               format(response.status_code, response.content))

        self.kernel = Kernel(self.ws_api_endpoint, kernel_id, timeout)
        return self.kernel

    def shutdown(self, kernel_id):
        print("Shutting down kernel : {} ....".format(kernel_id))
        if self.kernel:
            self.kernel.shutdown()

        if not kernel_id:
            return False
        url = "{}/{}".format(self.http_api_endpoint, kernel_id)
        response = requests.delete(url)
        if response.status_code == 204:
            print('Kernel {} shutdown'.format(kernel_id))
            return True
        else:
            raise RuntimeError('Error shutting down kernel {}: {}'.format(kernel_id, response.content))


class Kernel:

    DEAD_MSG_ID = 'deadbeefdeadbeefdeadbeefdeadbeef'
    POST_IDLE_TIMEOUT = 0.5

    def __init__(self, ws_api_endpoint, kernel_id, timeout=DEFAULT_TIMEOUT):

        self.shutting_down = False
        self.ws_api_endpoint = ws_api_endpoint
        self.kernel_api_endpoint = '{}/{}/channels'.format(ws_api_endpoint, kernel_id)
        self.kernel_id = kernel_id
        print('Initializing kernel client ({}) to {}'.format(kernel_id, self.kernel_api_endpoint))

        self.kernel_socket = websocket.create_connection(self.kernel_api_endpoint, timeout=timeout,
                                                         enable_multithread=True)

        self.response_queues = {}

        # startup reader thread
        self.response_reader = Thread(target=self._read_responses)
        self.response_reader.start()

    def shutdown(self):
        # Terminate thread, close socket and clear queues.
        self.shutting_down = True

        if self.kernel_socket:
            self.kernel_socket.close()
            self.kernel_socket = None

        if self.response_queues:
            self.response_queues.clear()
            self.response_queues = None

        if self.response_reader:
            self.response_reader = None

    def execute(self, code, timeout=DEFAULT_TIMEOUT):
        """
        Executes the code provided and returns the result of that execution.
        """
        response = []
        try:
            msg_id = self._send_request(code)

            post_idle = False
            while True:
                response_message = self._get_response(msg_id, timeout, post_idle)
                if response_message:
                    response_message_type = response_message['msg_type']

                    if response_message_type == 'error':
                        raise RuntimeError('ERROR: {}:{}'.format(response_message['content']['ename'],
                                                                 response_message['content']['evalue']))

                    if response_message_type == 'stream':
                        response.append(Kernel._convert_raw_response(response_message['content']['text']))

                    elif response_message_type == 'execute_result' or response_message_type == 'display_data':
                        if 'text/plain' in response_message['content']['data']:
                            response.append(
                                Kernel._convert_raw_response(response_message['content']['data']['text/plain']))
                        elif 'text/html' in response_message['content']['data']:
                            response.append(
                                Kernel._convert_raw_response(response_message['content']['data']['text/html']))

                    elif response_message_type == 'status':
                        if response_message['content']['execution_state'] == 'idle':
                            post_idle = True  # indicate we're at the logical end and timeout poll for next message
                            continue

                if post_idle and response_message is None:
                    break

        except BaseException as b:
            print(b)

        return '\n'.join(response)

    def _send_request(self, code):
        """
        Builds the request and submits it to the kernel.  Prior to sending the request it
        creates an empty response queue and adds it to the dictionary using msg_id as the
        key.  The msg_id is returned in order to read responses.
        """
        msg_id = uuid4().hex
        message = Kernel.__create_execute_request(msg_id, code)

        # create response-queue and add to map for this msg_id
        self.response_queues[msg_id] = queue.Queue()

        self.kernel_socket.send(message)

        return msg_id

    def _get_response(self, msg_id, timeout, post_idle):
        """
        Pulls the next response message from the queue corresponding to msg_id.  If post_idle is true,
        the timeout parameter is set to a very short value since a majority of time, there won't be a
        message in the queue.  However, in cases where a race condition occurs between the idle status
        and the execute_result payload - where the two are out of order, then this will pickup the result.
        """

        if post_idle and timeout > Kernel.POST_IDLE_TIMEOUT:
            timeout = Kernel.POST_IDLE_TIMEOUT  # overwrite timeout to small value following idle messages.

        msg_queue = self.response_queues.get(msg_id)
        try:
            response = msg_queue.get(timeout=timeout)

            print_str = '\n<<<<<<<<<<<<<<< POST IDLE MESSAGE >>>>>>>>>>>>>>>' if post_idle else '\n<<<<<<<<<<<<<<<'
            print(print_str)
            print('Pulled response from queue for kernel with msg_id: {}'.format(msg_id))
            pprint(response)

        except queue.Empty:
            response = None

        return response

    def _read_responses(self):
        """
        Reads responses from the websocket.  For each response read, it is added to the response queue based
        on the messages parent_header.msg_id.  It does this for the duration of the class's lifetime until its
        shutdown method is called, at which time the socket is closed (unblocking the reader) and the thread
        terminates.  If shutdown happens to occur while processing a response (unlikely), termination takes
        place via the loop control boolean.
        """
        try:
            while not self.shutting_down:
                raw_message = self.kernel_socket.recv()
                response_message = json_decode(utf8(raw_message))

                msg_id = Kernel._get_msg_id(response_message)

                if msg_id not in self.response_queues:  # this will happen when the msg_id is generated by the server
                    self.response_queues[msg_id] = queue.Queue()

                # insert into queue
                self.response_queues.get(msg_id).put_nowait(response_message)

            print('Response reader thread exiting...')

        except websocket.WebSocketConnectionClosedException:
            pass  # websocket closure most likely due to shutdown

        except BaseException as be:
            if not self.shutting_down:
                print('Unexpected exception encountered ({})'.format(be))

        print('Response reader thread exiting...')

    @staticmethod
    def _get_msg_id(message):

        msg_id = Kernel.DEAD_MSG_ID
        if message and 'msg_id' in message['parent_header'] and message['parent_header']['msg_id']:
            msg_id = message['parent_header']['msg_id']

        return msg_id

    @staticmethod
    def _convert_raw_response(raw_response_message):
        result = raw_response_message
        if isinstance(raw_response_message, str):
            if "u'" in raw_response_message:
                result = raw_response_message.replace("u'", "")[:-1]

        return result

    @staticmethod
    def __create_execute_request(msg_id, code):
        return json_encode({
            'header': {
                'username': '',
                'version': '5.0',
                'session': '',
                'msg_id': msg_id,
                'msg_type': 'execute_request'
            },
            'parent_header': {},
            'channel': 'shell',
            'content': {
                'code': code,
                'silent': False,
                'store_history': False,
                'user_expressions': {},
                'allow_stdin': False
            },
            'metadata': {},
            'buffers': {}
        })
