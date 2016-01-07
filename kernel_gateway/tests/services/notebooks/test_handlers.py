from kernel_gateway.services.notebooks.handlers import NotebookAPIHandler
import json
import unittest

class TestFormatRequestCode(unittest.TestCase):

    def test_format_request_code_not_escaped(self):
        '''Test formatting request code without escaped quotes'''
        test_request = ('{"body": "", "headers": {"Accept-Language": "en-US,en;q=0.8", '
                        '"If-None-Match": "9a28a9262f954494a8de7442c63d6d0715ce0998", '
                        '"Accept-Encoding": "gzip, deflate, sdch"}, "args": {}, "path": {}}')
        request_code = NotebookAPIHandler._format_request(None, test_request)
        #Get the value of REQUEST = "{ to test for equality
        test_request_js_value = request_code[request_code.index("\"{"):]
        self.assertEqual(test_request, json.loads(test_request_js_value), "Request code without escaped quotes was not formatted correctly")

    def test_format_request_code_escaped(self):
        '''Test formatting request code where multiple escaped quotes exist'''
        test_request = ('{"body": "", "headers": {"Accept-Language": "en-US,en;q=0.8", '
                        '"If-None-Match": "\"\"9a28a9262f954494a8de7442c63d6d0715ce0998\"\"", '
                        '"Accept-Encoding": "gzip, deflate, sdch"}, "args": {}, "path": {}}')
        request_code = NotebookAPIHandler._format_request(None, test_request)
        #Get the value of REQUEST = "{ to test for equality
        test_request_js_value = request_code[request_code.index("\"{"):]
        self.assertEqual(test_request, json.loads(test_request_js_value), "Escaped Request code was not formatted correctly")