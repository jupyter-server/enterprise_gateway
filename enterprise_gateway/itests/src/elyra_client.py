import os
from tornado.escape import json_encode, json_decode, url_escape
from uuid import uuid4
import websocket
import requests


class ElyraClient(object):
    execute_message = {
        'header': {'username': '', 'version': '5.0', 'session': '', 'msg_id': "", 'msg_type': 'execute_request'},
        'parent_header': {}, 'channel': 'shell', 'metadata': {}, 'buffers': {},
        'content': {'silent': False, 'store_history': False, 'user_expressions': {}, 'allow_stdin': False}}

    def __init__(self, host, username):
        self.http_api_endpoint = "http://{}/api/kernels".format(host)
        self.ws_endpoint = "ws://{}/api/kernels".format(host)
        self.username = username

    def delete_kernel(self, kernel_id):
        if not kernel_id:
            return False
        url = "{}/{}".format(self.http_api_endpoint, kernel_id)
        response = requests.delete(url)
        return response.status_code == 204

    def create_kernel(self, kernel_spec_name):
        # Ask Elyra to create a new kernel based on kernel spec name, and return the kernel id if successfully created.
        kernel_id = None
        json_data = {'name': kernel_spec_name}
        if self.username is not None:
            json_data['env'] = {'KERNEL_USERNAME': self.username}
        response = requests.post(self.http_api_endpoint, data=json_encode(json_data))
        if response.status_code == 201:
            json_data = response.json()
            kernel_id = json_data.get("id")
        return kernel_id

    def get_ws_kernel_endpoint(self, kernel_id):
        # Given a kernel id, return the corresponding web socket endpoint for this kernel to send/receive messages.
        return "{}/{}/channels".format(self.ws_endpoint, url_escape(kernel_id))

    @staticmethod
    def new_code_message(code):
        ElyraClient.execute_message["header"]["msg_id"] = uuid4().hex
        ElyraClient.execute_message["content"]["code"] = code
        return json_encode(ElyraClient.execute_message)

    @staticmethod
    def receive_target_messages(ws, target_msg_type_queue):
        """
        Given a web socket connection, after sending one message, we may receive multiple
        messages back, e.g. status, execute_input, stream.
        Here only find those target message type and return its content in a list.
        """
        message_json_list = list([])
        while target_msg_type_queue:
            try:
                message = ws.recv()
                message_json = json_decode(message)
                # DEBUG: Enable for easier debugging
                # print("message: {}".format(message_json))
                msg_type = message_json.get('msg_type')
                if msg_type == target_msg_type_queue[0]:
                    target_msg_type_queue.popleft()  # find one target, remove from queue
                    message_json_list.append(message_json)
                if msg_type == "error":
                    raise Exception("Error found when receiving message:\n{}".format(message_json))
                if msg_type == "status":  # detect kernel restart, treat as failure
                    msg_content = message_json.get('content')
                    if msg_content:
                        msg_state = msg_content.get('execution_state')
                        if msg_state:
                            if msg_state == 'restarting':
                                raise Exception("Request failed: kernel restarting\n{}".format(message_json))
            except ValueError as e:
                # Ignore No JSON object could be decoded error, continue to the next message.
                if str(e).find("No JSON object could be decoded") > 0:
                    print(e)
                    continue
                else:
                    raise e

        return message_json_list
