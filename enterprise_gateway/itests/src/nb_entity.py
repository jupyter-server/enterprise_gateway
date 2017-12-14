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

    def __init__(self, nb_file_path):
        self.nb_file_path = nb_file_path
        self.kernel_id = None
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

    def test_notebook(self, count, nb_test_case):
        #  Creates a kernel, tests the cells, then deletes the kernel.
        errors = 0
        self.kernel_id = nb_test_case.elyra_client.create_kernel(self.kernel_spec_name)
        print("\n{}. {}".format(count, self))
        if self.kernel_id:
            try:
                errors = self.test_cells(nb_test_case)
            finally:
                nb_test_case.elyra_client.delete_kernel(self.kernel_id)
        return errors

    def test_cells(self, nb_test_case):
        # Execute all code cells in a notebook code entity, get the response message in JSON format,
        # and return all code cells parsed by messages in a list.
        errors = 0
        ws_url = nb_test_case.elyra_client.get_ws_kernel_endpoint(self.kernel_id)
        ws = websocket.create_connection(url=ws_url, timeout=itest_cell_timeout)
        print("Connection created for web socket {}".format(ws_url))
        try:
            code_cell_count = 1
            for code_cell in self.code_cell_list:
                if code_cell.is_executed():
                    errors = errors + NBCodeEntity.test_cell(nb_test_case, ws, code_cell, code_cell_count)
                code_cell_count = code_cell_count+1
        finally:
            ws.close()
        return errors

    @staticmethod
    def test_cell(nb_test_case, ws, code_cell, code_cell_count):
        print("\n--- {}) {}\n{}".format(code_cell_count, code_cell,
                                      code_cell.get_source_for_execution()))
        code_source = code_cell.get_source_for_execution()
        ws.send(ElyraClient.new_code_message(code_source))
        target_queue = code_cell.get_target_output_type_queue()
        if code_cell.is_output_empty():
            # If output empty, waiting for "execute_input" type message
            target_queue = deque(["execute_input"])
        try:
            json_output_message = ElyraClient.receive_target_messages(ws, target_queue)
        except websocket.WebSocketTimeoutException as wste:
            print("Fail ===================================\nRequest timed out.")
            return 1
        except Exception as e:
            print("FATAL ===================================\n{}.".format(e))
            raise e

        result_cell = NBCodeCell(message_json_list=json_output_message)
        return NBCodeEntity.compare_results(nb_test_case, code_cell, result_cell)

    @staticmethod
    def compare_results(nb_test_case, orig_cell, result_cell):
        nb_test_case.assertIsNotNone(result_cell)
        assert_code = NBCodeEntity.get_assert_code(orig_cell.get_first_line_code())
        result_output_str = result_cell.serialize_output()
        print(">>> {}".format(result_output_str))
        orig_output_str = orig_cell.serialize_output()
        try:
            if assert_code != 2:
                if assert_code == 0:
                    nb_test_case.assertEqual(result_output_str, orig_output_str)
                elif assert_code == 1:
                    nb_test_case.assertNotEqual(result_output_str, orig_output_str)
                elif assert_code == 3 and nb_test_case.enforce_impersonation:
                    # Do impersonation test if and only if the first line is IMPERSONATION (assert code = 3)
                    # and self.enforce_impersonation is True
                    test_username = result_cell.code_output_list[0].raw_output.get('text')
                    print("Now doing impersonation test, target username={}, test username={}".format(
                        nb_test_case.username, test_username))
                    nb_test_case.assertIsNotNone(test_username)
                    # the raw output is a dict e.g. {'text': 'elyra\r\n', ...}, so here replace the \r\n
                    test_username = str(test_username).replace("\r\n", "")
                    nb_test_case.assertEqual(test_username, nb_test_case.username)
            print("Pass")
        except Exception as e:
            print("Fail ===================================")
            print("Expected output: '{}'".format(orig_output_str))
            print("Actual output:   '{}'".format(result_output_str))
            if not nb_test_case.continue_when_error:
                raise e
            return 1
        return 0

    @staticmethod
    def get_assert_code(first_line_code):
        """
        Given the first line of the source code, return the code for testing purposes:
        0 : must be exactly the same, i.e. using assertEqual (default)
        1 : must not be the same as each time the execution will definitely be different, then use assertNotEqual
        2 : OK if test output not the same as input, i.e. ignore assert as long as no error
        3 : Impersonation test, i.e. compare the output username if the self.enforce_impersonation is set as True
        """
        if first_line_code:
            if first_line_code.find("DIFFERENT") > 0:
                return 1
            elif first_line_code.find("DEPENDS") > 0:
                return 2
            elif first_line_code.find("IMPERSONATION") > 0:
                return 3
        return 0

    def __repr__(self):
        return "Kernel ID: {}, Notebook: {}, Kernel spec: {}, Number of code cells: {}".\
            format(self.kernel_id, self.file_name, self.kernel_spec_name, len(self.code_cell_list))
