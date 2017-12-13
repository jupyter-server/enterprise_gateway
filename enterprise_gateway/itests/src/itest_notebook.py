from unittest import TestCase
from elyra_client import ElyraClient


class NotebookTestCase(TestCase):

    def __init__(self, test_method, nb_entities_list, **kwargs):
        TestCase.__init__(self, methodName=test_method)
        self.nb_entities_list = nb_entities_list
        self.continue_when_error = kwargs.get("continue_when_error")
        self.username = kwargs.get("username")
        self.elyra_client = ElyraClient(host=kwargs.get("host"), username=self.username)
        self.enforce_impersonation = kwargs.get("enforce_impersonation")
        print("NotebookTestCase arguments: {}\n".format(kwargs))

    def test_kernels_batch(self):
        test_count = 1
        errors = 0
        print("Begin testing batch of {} notebook(s)...".format(len(self.nb_entities_list)))
        for nb_code_entity in self.nb_entities_list:
            try:
                errors = errors + nb_code_entity.test_notebook(test_count, self)
            except Exception as e:
                errors = errors + 1
            test_count = test_count + 1
        print("\nBatch completed.")
        self.assertEquals(0, errors)
