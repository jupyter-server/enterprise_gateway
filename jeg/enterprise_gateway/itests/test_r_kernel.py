import os
import unittest

from enterprise_gateway.client.gateway_client import GatewayClient

from .test_base import TestBase


class RKernelBaseTestCase(TestBase):
    """
    R related test cases common to vanilla IRKernel kernels
    """

    def test_get_hostname(self):
        result, has_error = self.kernel.execute('system("hostname", intern=TRUE)')
        self.assertRegex(result, self.get_expected_hostname())
        self.assertEqual(has_error, False)

    def test_hello_world(self):
        result, has_error = self.kernel.execute('print("Hello World", quote = FALSE)')
        self.assertRegex(result, "Hello World")
        self.assertEqual(has_error, False)

    def test_restart(self):
        # 1. Set a variable to a known value.
        # 2. Restart the kernel
        # 3. Attempt to increment the variable, verify an error was received (due to undefined variable)

        self.kernel.execute("x = 123")
        original_value, has_error = self.kernel.execute("write(x,stdout())")
        self.assertEqual(int(original_value), 123)
        self.assertEqual(has_error, False)

        self.assertTrue(self.kernel.restart())

        error_result, has_error = self.kernel.execute("y = x + 1")
        self.assertRegex(error_result, "Error in eval")
        self.assertEqual(has_error, True)

    def test_interrupt(self):
        # 1. Set a variable to a known value.
        # 2. Spawn a thread that will perform an interrupt after some number of seconds,
        # 3. Issue a long-running command - that spans during of interrupt thread wait time,
        # 4. Interrupt the kernel,
        # 5. Attempt to increment the variable, verify expected result.

        self.kernel.execute("x = 123")
        original_value, has_error = self.kernel.execute("write(x,stdout())")
        self.assertEqual(int(original_value), 123)
        self.assertEqual(has_error, False)

        # Start a thread that performs the interrupt.  This thread must wait long enough to issue
        # the next cell execution.
        self.kernel.start_interrupt_thread()

        # Build the code list to interrupt, in this case, its a sleep call.
        interrupted_code = []
        interrupted_code.append('write("begin",stdout())\n')
        interrupted_code.append("Sys.sleep(30)\n")
        interrupted_code.append('write("end",stdout())\n')
        interrupted_result, has_error = self.kernel.execute(interrupted_code)

        # Ensure the result indicates an interrupt occurred
        self.assertEqual(interrupted_result.strip(), "begin")
        self.assertEqual(has_error, False)

        # Wait for thread to terminate - should be terminated already
        self.kernel.terminate_interrupt_thread()

        # Increment the pre-interrupt variable and ensure its value is correct
        self.kernel.execute("y = x + 1")
        interrupted_value, has_error = self.kernel.execute("write(y,stdout())")
        self.assertEqual(int(interrupted_value), 124)
        self.assertEqual(has_error, False)


class RKernelBaseSparkTestCase(RKernelBaseTestCase):
    """
    R related tests cases common to Spark on Yarn
    """

    def test_get_application_id(self):
        result, has_error = self.kernel.execute(
            'SparkR:::callJMethod(SparkR:::callJMethod(sc, "sc"), "applicationId")'
        )
        self.assertRegex(result, self.get_expected_application_id())
        self.assertEqual(has_error, False)

    def test_get_spark_version(self):
        result, has_error = self.kernel.execute("sparkR.version()")
        self.assertRegex(result, self.get_expected_spark_version())
        self.assertEqual(has_error, False)

    def test_get_resource_manager(self):
        result, has_error = self.kernel.execute('unlist(sparkR.conf("spark.master"))')
        self.assertRegex(result, self.get_expected_spark_master())
        self.assertEqual(has_error, False)

    def test_get_deploy_mode(self):
        result, has_error = self.kernel.execute('unlist(sparkR.conf("spark.submit.deployMode"))')
        self.assertRegex(result, self.get_expected_deploy_mode())
        self.assertEqual(has_error, False)


class TestRKernelLocal(unittest.TestCase, RKernelBaseTestCase):
    KERNELSPEC = os.getenv("R_KERNEL_LOCAL_NAME", "ir")  # R_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting R kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down R kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestRKernelClient(unittest.TestCase, RKernelBaseSparkTestCase):
    KERNELSPEC = os.getenv(
        "R_KERNEL_CLIENT_NAME", "spark_R_yarn_client"
    )  # spark_R_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        print(f"\nStarting R kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down R kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestRKernelCluster(unittest.TestCase, RKernelBaseSparkTestCase):
    KERNELSPEC = os.getenv(
        "R_KERNEL_CLUSTER_NAME", "spark_R_yarn_cluster"
    )  # spark_R_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting R kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down Python kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


if __name__ == "__main__":
    unittest.main()
