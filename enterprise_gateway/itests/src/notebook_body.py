# -*- coding: utf-8 -*-

import os
import json
import websocket
from collections import deque
from elyra_client import ElyraClient

itest_cell_timeout = int(os.getenv('ITEST_CELL_TIMEOUT', 30))


class CodeCellOutput(object):
    # A prototype class for the output of a cell whose type is "code"
    def __init__(self, json_output, output_type):
        self.raw_output = json_output
        self.output_type = output_type
        self.output = self.parse_output()

    def parse_output(self):
        # need different ways to parse the code_output format
        raise NotImplementedError

    @staticmethod
    def build_code_cell(output_type, output):
        if output_type == "stream":
            return StreamOutput(json_output=output)
        elif output_type == "execute_result":
            return ExecuteResult(json_output=output)
        elif output_type == "display_data":
            return DisplayData(json_output=output)
        elif output_type == "error":
            return Error(json_output=output)
        return None

    def serialize(self):
        output_list = list()
        if type(self.output) is dict:
            # in the case of dict type data, the keys might be in arbitrary order
            # so here sort the key and serialize values in order so as to compare the values by the order of keys
            sorted_key_list = sorted(self.output.keys())
            first = True
            for k in sorted_key_list:
                if first:
                    first = False
                else:
                    output_list.append(",")

                val = self.output[k]
                if type(val) is list:
                    output_list.append("".join(val))
                else:
                    output_list.append(str(val))
        elif type(self.output) is list:
            output_list = self.output
        else:
            output_list.append(self.output)

        output = "".join(output_list).replace("\n", "")
        return output


class StreamOutput(CodeCellOutput):

    def __init__(self, json_output):
        CodeCellOutput.__init__(self, json_output, "stream")
        self.name = self.raw_output.get("name")

    def parse_output(self):
        return self.raw_output.get("text")


class DisplayData(CodeCellOutput):
    def __init__(self, json_output):
        CodeCellOutput.__init__(self, json_output, "display_data")

    def parse_output(self):
        return self.raw_output.get("data")


class ExecuteResult(CodeCellOutput):
    def __init__(self, json_output):
        CodeCellOutput.__init__(self, json_output, "execute_result")

    def parse_output(self):
        return self.raw_output.get("data")


class Error(CodeCellOutput):
    def __init__(self, json_output):
        CodeCellOutput.__init__(self, json_output, "error")
        self.ename = self.evalue = self.traceback = None

    def parse_output(self):
        self.ename = self.raw_output.get("ename")
        self.evalue = self.raw_output.get("evalue")
        self.traceback = self.raw_output.get("traceback")
        return "{}\n{}\n{}".format(self.ename, self.evalue, self.traceback)


class NBCodeCell(object):
    # An object represent a code cell in a notebook .ipynb file.
    # May contain different types of code outputs, e.g. stream, display data
    def __init__(self, cell_json=None, message_json_list=None):
        self.code_source_list = list([])
        self.code_output_list = list([])
        self.execute_count = None
        if cell_json:
            self.code_source_list = cell_json.get("source")
            self.execute_count = cell_json.get("execution_count")
            self.code_output_list = NBCodeCell.parse_output_from_notebook(cell_json)
        elif message_json_list:
            self.code_output_list = NBCodeCell.parse_output_from_message(message_json_list)

    def is_executed(self):
        # Check if this code is literally executed
        return self.execute_count is not None

    def get_source_for_execution(self):
        # A cell's source can have multiple lines of code, but here returns the source as a single string,
        # since executing a multi-line code v.s. line by line may generate different results.
        return "".join(self.code_source_list)

    def is_output_empty(self):
        # Check if a cell has any output in it, as in some cases, the code cell output can be empty,
        # e.g. define a function/class or import a package.
        for output in self.code_output_list:
            if output:
                return False
        return True

    def get_first_line_code(self):
        first_line = self.code_source_list[0] if self.code_source_list else None
        return str(first_line).upper()

    def get_target_output_type_queue(self):
        # Return all output types as a queue, FIFO
        target_output_type_queue = deque([])
        for co in self.code_output_list:
            target_output_type_queue.append(co.output_type)
        return target_output_type_queue

    def __repr__(self):
        return "{} line(s) of code, {} output(s)".format(len(self.code_source_list), len(self.code_output_list))

    @staticmethod
    def parse_output_from_notebook(nb_cell_json):
        # Build a list of code cell output entity from notebook json file,
        # since a code cell in notebook json file can have multiple output.
        cell_output_list = list([])
        if nb_cell_json and type(nb_cell_json) is dict:
            if nb_cell_json.get("cell_type") == "code" and "outputs" in nb_cell_json:
                json_output_list = nb_cell_json.get("outputs")
                for output in json_output_list:
                    cell_output = CodeCellOutput.build_code_cell(output.get("output_type"), output)
                    cell_output_list.append(cell_output)
        return cell_output_list

    @staticmethod
    def parse_output_from_message(message_json_list):
        # Build a list of code cell output from a list of json message received from socket
        cell_output_list = list([])
        if message_json_list:
            for message_json in message_json_list:
                cell_output = CodeCellOutput.build_code_cell(message_json.get("msg_type"), message_json.get("content"))
                cell_output_list.append(cell_output)
        return cell_output_list

    def serialize_output(self):
        str_list = []
        for code_cell_output in self.code_output_list:
            if code_cell_output:
                str_list.append(code_cell_output.serialize())
        return "".join(str_list)


class NBCodeEntity(object):
    # An object represent all code cells inside a NB

    def __init__(self, nb_file_path, host):
        # C
        self.nb_file_path = nb_file_path
        self.kernel_id = None
        self.host = host
        if os.path.exists(nb_file_path):
            self.file_name = os.path.split(nb_file_path)[1]
            nb_file = open(nb_file_path, mode='r')
            nb_json = json.load(fp=nb_file)
            self.code_cell_list = list([])
            kernel_spec = nb_json["metadata"]["kernelspec"]
            self.kernel_spec_name = kernel_spec["name"]
            for cell in nb_json.get("cells"):
                if cell.get("cell_type") == "code":
                    code_cell = NBCodeCell(cell_json=cell)
                    self.code_cell_list.append(code_cell)
            nb_file.close()
        else:
            raise IOError("No such file provided: {}".format(nb_file_path))

    def get_all_code_cell_output(self):
        res_list = list([])
        for code_cell in self.code_cell_list:
            for output in code_cell.code_output_list:
                res_list.append(output)
        return res_list

    def run_cell(self, cell_number):
        ws_url = ElyraClient.get_ws_kernel_endpoint(self.kernel_id, self.host)
        try:
            ws = websocket.create_connection(ws_url)
            # print("Connection created for web socket {}".format(ws_url))
        except (RuntimeError, TypeError, NameError):
            print("Could not create websocket connection")
        code_cell = self.code_cell_list[cell_number-1]
        print("\n--- {}\n{}".format(code_cell,
                                    code_cell.get_source_for_execution()))
        code_source = code_cell.get_source_for_execution()
        ws.send(ElyraClient.new_code_message(code_source))
        target_queue = code_cell.get_target_output_type_queue()
        if code_cell.is_output_empty():
            # If output empty, waiting for "execute_input" type message
            target_queue = deque(["execute_input"])
        try:
            json_output_message = ElyraClient.receive_target_messages(ws, target_queue)
            # print("JSON OUTPUT: {}".format(json_output_message)) #DEBUG
        except websocket.WebSocketTimeoutException as wste:
            print("Fail ===================================\nRequest timed out.")
            return 1
        except Exception as e:
            print("FATAL ===================================\n{}.".format(e))
            raise e
        result_cell = NBCodeCell(message_json_list=json_output_message)
        print("Result was : {}".format(result_cell.serialize_output()))
        return result_cell.serialize_output().strip()

    def __repr__(self):
        return "Kernel ID: {}, Notebook: {}, Kernel spec: {}, Number of code cells: {}".\
            format(self.kernel_id, self.file_name, self.kernel_spec_name, len(self.code_cell_list))
