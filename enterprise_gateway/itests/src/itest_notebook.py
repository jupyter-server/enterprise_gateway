from unittest import TestCase
from elyra_client import ElyraClient
import traceback
import sys


class NotebookTestCase(TestCase):

    def __init__(self, test_method, nb_entities_list, continue_when_error, host, username):
        TestCase.__init__(self, methodName=test_method)
        self.nb_entities_list = nb_entities_list
        self.continue_when_error = continue_when_error
        self.elyra_client = ElyraClient(host=host, username=username)

    @staticmethod
    def get_assert_code(first_line_code):
        """
        Given the first line of the source code, return the code for testing purposes:
        0 : must be exactly the same, i.e. using assertEqual (default)
        1 : OK if test output not the same as input, i.e. ignore assert as long as no error
        2 : must not be the same as each time the execution will definitely be different, then use assertNotEqual
        """
        if first_line_code:
            if first_line_code.find("DIFFERENT") > 0:
                return 1
            elif first_line_code.find("DEPENDS") > 0:
                return 2
        return 0

    def execute_codes(self, nb_code_entity):
        nb_code_entity.kernel_id = self.elyra_client.create_new_kernel(nb_code_entity)
        self.test_count += 1
        print("\n{}. {}".format(self.test_count, nb_code_entity))
        test_code_cell_output_list = None
        if nb_code_entity.kernel_id:
            try:
                test_code_cell_output_list = self.elyra_client.execute_nb_code_entity(nb_code_entity)
            except Exception as e:
                print(e.message, traceback.format_exc())
                if not self.continue_when_error:
                    print("Failed to execute the codes, now exit.")
                    sys.exit(-1)
            finally:
                self.elyra_client.delete_kernel(nb_code_entity.kernel_id)
            return test_code_cell_output_list

    def execute_and_assert(self, nb_code_entity):
        test_code_cell_list = self.execute_codes(nb_code_entity)
        print("\nFinish execution of codes, now compare/assert")
        self.assertIsNotNone(test_code_cell_list)
        self.assertEqual(len(test_code_cell_list), len(nb_code_entity.code_cell_list))
        index = 0
        for real_code_cell in nb_code_entity.code_cell_list:
            if real_code_cell.is_executed() and not real_code_cell.is_output_empty():
                test_output = test_code_cell_list[index]
                self.assertIsNotNone(test_output)
                assert_code = NotebookTestCase.get_assert_code(real_code_cell.get_first_line_code())
                test_output = test_output.seralize_output()
                real_output = real_code_cell.seralize_output()
                try:
                    if assert_code != 2:
                        if assert_code == 0:
                            self.assertEqual(test_output, real_output)
                        elif assert_code == 1:
                            self.assertNotEqual(test_output, real_output)
                except Exception as e:
                    print("===================================")
                    print(e.message)
                    print(traceback.format_exc())
                    print("{}\nExecute count {}".format(nb_code_entity, real_code_cell.execute_count))
                    print("[Test output]\n", test_output)
                    print("[Real output]\n", real_output)
                    if not self.continue_when_error:
                        sys.exit(-1)
            index += 1
        print("Testing completed: {}".format(nb_code_entity))

    def test_kernels_batch(self):
        self.test_count = 0
        print("Begin testing batch of {} notebook(s)...\n".format(len(self.nb_entities_list)))
        for nb_code_entity in self.nb_entities_list:
            self.execute_and_assert(nb_code_entity)
        print("\nBatch completed.")
