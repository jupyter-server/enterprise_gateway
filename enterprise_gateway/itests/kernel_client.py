
import os
import requests

from uuid import uuid4
# from pprint import pprint
from tornado.escape import json_encode, json_decode, utf8
from tornado.websocket import websocket_connect
from tornado.ioloop import IOLoop
from tornado.httpclient import HTTPRequest


class KernelLauncher:
    DEFAULT_USERNAME = os.getenv('KERNEL_USERNAME', 'bob')
    DEFAULT_GATEWAY_HOST = os.getenv('GATEWAY_HOST', 'localhost:8888')

    def __init__(self, host=DEFAULT_GATEWAY_HOST):
        self.http_api_endpoint = 'http://{}/api/kernels'.format(host)
        self.ws_api_endpoint = 'ws://{}/api/kernels'.format(host)

    def launch(self, kernelspec_name, username=DEFAULT_USERNAME):
        print('Launching a {} kernel ....'.format(kernelspec_name))
        kernel_id = None
        json_data = {'name': kernelspec_name}
        if username is not None:
            json_data['env'] = {'KERNEL_USERNAME': username}
        response = requests.post(self.http_api_endpoint, data=json_encode(json_data))
        if response.status_code == 201:
            json_data = response.json()
            kernel_id = json_data.get("id")
            print('Launched kernel with id {}'.format(kernel_id))
        else:
            raise RuntimeError('Error creating kernel : {} response code \n {}'.format(response.status_code, response.content))

        return Kernel(self.ws_api_endpoint, kernel_id)

    def shutdown(self, kernel_id):
        print("Shutting down kernel : {} ....".format(kernel_id))
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
    DEFAULT_TIMEOUT = 60 * 60

    def __init__(self, ws_api_endpoint, kernel_id):
        self.ws_api_endpoint = ws_api_endpoint
        self.kernel_api_endpoint = '{}/{}/channels'.format(ws_api_endpoint, kernel_id)
        self.kernel_id = kernel_id
        print('Initializing kernel client ({}) to {}'.format(kernel_id, self.kernel_api_endpoint))


    def __create_execute_request(self, msg_id, code):
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

    def execute(self, code, timeout=DEFAULT_TIMEOUT):

        kernel_socket = None
        response_type = None
        response = []

        #print('')
        #print('Submitting code:\n{}'.format(code))
        #print('')

        try:
            ws_req = HTTPRequest(self.kernel_api_endpoint)
            kernel_socket_future = websocket_connect(ws_req)
            kernel_socket = IOLoop.current().run_sync(lambda: kernel_socket_future, timeout)

            #pprint('')
            #print('>>>>> Sending message to kernel')
            msg_id = uuid4().hex
            message = self.__create_execute_request(msg_id, code)
            #pprint(message)
            future = kernel_socket.write_message(message)
            response_message = IOLoop.current().run_sync(lambda: future, timeout)

            while True:
                msg_future = kernel_socket.read_message()
                response_message = IOLoop.current().run_sync(lambda: msg_future, timeout)

                response_message = json_decode(utf8(response_message))

                #pprint('>>>>>>>>>>>>>>>>>>>')
                #print('Received message from kernel')
                #pprint(response_message)

                # Ensure this message is for us (ids match)
                if 'msg_id' not in response_message['parent_header'] or response_message['parent_header']['msg_id'] != msg_id:
                    continue

                response_message_type = response_message['msg_type']

                if response_message_type == 'error':
                    raise RuntimeError('ERROR: {}:{}'.format(response_message['content']['ename'], response_message['content']['evalue']))

                if response_message_type == 'stream':
                    response_type = 'text'
                    response.append(self._process_response_message(response_message['content']['text']))

                if response_message_type == 'execute_result' or response_message_type == 'display_data':
                    if 'text/plain' in response_message['content']['data']:
                        response_type = 'text'
                        response.append(self._process_response_message(response_message['content']['data']['text/plain']))
                    elif 'text/html' in response_message['content']['data']:
                        response_type = 'html'
                        response.append(self._process_response_message(response_message['content']['data']['text/html']))
                    continue

                elif response_message_type == 'status':
                    if response_message['content']['execution_state'] == 'idle':
                        break

        except BaseException as b:
            print(b)

        #finally:
        #    if kernel_socket_future:
        #        try:
        #            kernel_socket_future.close()
        #            kernel_socket_future = None
        #        finally:
        #            # ignore
        #            print('Error closing kernel socket.')


        return '\n'.join(response)


    def _process_response_message(self, raw_response_message):
        result = raw_response_message
        if isinstance(raw_response_message, str):
            if "u'" in raw_response_message:
                result = raw_response_message.replace("u'", "")[:-1]

        return result