import unittest
import os
from enterprise_gateway.client.gateway_client import GatewayClient


class TestAuthorization(unittest.TestCase):
    KERNELSPEC = os.getenv("AUTHORIZATION_KERNEL_NAME", "authorization_test")

    @classmethod
    def setUpClass(cls):
        super(TestAuthorization, cls).setUpClass()
        print('>>>')

        # initialize environment
        cls.gateway_client = GatewayClient()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_authorized_users_when_all_values_are_passed(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel('authorization_complete', username='authorized_user_1')
            result = kernel.execute("print('The cow jumped over the moon.')")
            self.assertEquals(result, "The cow jumped over the moon.\n")
        finally:
            if kernel:
                kernel.shutdown()

    def test_authorized_users_when_only_authorized_values_are_passed(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel('authorization_authorized', username='authorized_user_1')
            result = kernel.execute("print('The cow jumped over the moon.')")
            self.assertEquals(result, "The cow jumped over the moon.\n")
        finally:
            if kernel:
                kernel.shutdown()

    def test_authorized_users_when_no_values_are_passed(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel('authorization_empty', username='authorized_user_1')
            result = kernel.execute("print('The cow jumped over the moon.')")
            self.assertEquals(result, "The cow jumped over the moon.\n")
        finally:
            if kernel:
                kernel.shutdown()

    def test_unauthorized_users_when_all_values_are_passed(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel('authorization_complete', username='unauthorized_user_1')
            self.assertTrue(False, msg="Unauthorization exception expected!")
        except Exception as be:
            self.assertRegex(be.args[0], "403")
        finally:
            if kernel:
                kernel.shutdown()

    def test_unauthorized_users_when_only_unauthorized_values_are_passed(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel('authorization_unauthorized', username='unauthorized_user_1')
            self.assertTrue(False, msg="Unauthorization exception expected!")
        except Exception as be:
            self.assertRegex(be.args[0], "403")
        finally:
            if kernel:
                kernel.shutdown()

    def test_unauthorized_users_when_no_unauthorized_values_are_passed(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel('authorization_empty', username='unauthorized_user_1')
            result = kernel.execute("print('The cow jumped over the moon.')")
            self.assertEquals(result, "The cow jumped over the moon.\n")
        finally:
            if kernel:
                kernel.shutdown()

if __name__ == '__main__':
    unittest.main()