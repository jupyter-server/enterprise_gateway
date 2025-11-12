import os
import unittest

from enterprise_gateway.client.gateway_client import GatewayClient


class TestAuthorization(unittest.TestCase):
    KERNELSPEC = os.getenv("AUTHORIZATION_KERNEL_NAME", "authorization_test")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # initialize environment
        cls.gateway_client = GatewayClient()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_authorized_users(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel(TestAuthorization.KERNELSPEC, username="bob")
            result, has_error = kernel.execute("print('The cow jumped over the moon.')")
            self.assertEqual(result, "The cow jumped over the moon.\n")
            self.assertEqual(has_error, False)
        finally:
            if kernel:
                self.gateway_client.shutdown_kernel(kernel)

    def test_unauthorized_users(self):
        kernel = None
        try:
            kernel = self.gateway_client.start_kernel(
                TestAuthorization.KERNELSPEC, username="bad_guy"
            )
            self.assertTrue(False, msg="Unauthorization exception expected!")
        except Exception as be:
            self.assertRegex(be.args[0], "403")
        finally:
            if kernel:
                self.gateway_client.shutdown_kernel(kernel)


if __name__ == "__main__":
    unittest.main()
