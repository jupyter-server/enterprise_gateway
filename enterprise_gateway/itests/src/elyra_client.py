from tornado.escape import json_encode, json_decode, url_escape
from uuid import uuid4
from nb_entity import NBCodeCell
import websocket
from collections import deque

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

    def create_new_kernel(self, nb_code_entity):
        # Ask Elyra to create a new kernel based on kernel spec name, and return the kernel id if successfully created.
        kernel_id = None
        kernel_spec_name = nb_code_entity.kernel_spec_name
        response = requests.post(self.http_api_endpoint, data=json_encode({'name': kernel_spec_name, 'env' : {'KERNEL_USERNAME': self.username}}))
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
                msg_type = message_json.get('msg_type')
                if msg_type == target_msg_type_queue[0]:
                    target_msg_type_queue.popleft()  # find one target, remove from queue
                    message_json_list.append(message_json)
                if msg_type == "error":
                    raise Exception("Error found when receiving message:\n{}".format(message_json))
            except ValueError as e:
                # Ignore No JSON object could be decoded error, continue to the next message.
                if e.message == "No JSON object could be decoded":
                    print(e.message)
                    continue
                else:
                    raise e
        return message_json_list

    def execute_nb_code_entity(self, nb_code_entity):
        # Execute all code cells in a notebook code entity, get the response message in JSON format,
        # and return all code cells parsed by messages in a list.
        ws_url = self.get_ws_kernel_endpoint(nb_code_entity.kernel_id)
        ws = websocket.create_connection(url=ws_url)
        print("Connection created for web socket {}".format(ws_url))
        message_code_cell_list = list([])
        try:
            code_cell_count = 1
            for code_cell in nb_code_entity.get_all_code_cell():
                if code_cell.is_executed():
                    print("---{}) {}".format(code_cell_count, code_cell))
                    print("{}".format(code_cell.get_source_for_execution()))
                    code_cell_count += 1
                    code_source = code_cell.get_source_for_execution()
                    ws.send(ElyraClient.new_code_message(code_source))
                    target_queue = code_cell.get_target_output_type_queue()
                    if code_cell.is_output_empty():
                        # If output empty, waiting for "execute_input" type message
                        target_queue = deque(["execute_input"])
                    json_output_message = ElyraClient.receive_target_messages(ws, target_queue)
                    msg_code_cell = NBCodeCell(message_json_list=json_output_message)
                    message_code_cell_list.append(msg_code_cell)
        finally:
            ws.close()
        return message_code_cell_list
