import os
import unittest

from enterprise_gateway.client.gateway_client import GatewayClient

from .test_base import TestBase


class ScalaKernelBaseTestCase(TestBase):
    """
    Scala related test cases common to vanilla Scala kernels
    """

    def test_get_hostname(self):
        result = self.kernel.execute(
            "import java.net._; \
                                      val localhost: InetAddress = InetAddress.getLocalHost; \
                                      val localIpAddress: String = localhost.getHostName"
        )
        self.assertRegex(result, self.get_expected_hostname())

    def test_hello_world(self):
        result = self.kernel.execute('println("Hello World")')
        self.assertRegex(result, "Hello World")

    def test_restart(self):

        # 1. Set a variable to a known value.
        # 2. Restart the kernel
        # 3. Attempt to increment the variable, verify an error was received (due to undefined variable)

        self.kernel.execute("var x = 123")
        original_value = int(self.kernel.execute("x"))  # This will only return the value.
        self.assertEqual(original_value, 123)

        self.assertTrue(self.kernel.restart())

        error_result = self.kernel.execute("var y = x + 1")
        self.assertRegex(error_result, "not found: value x")

    def test_interrupt(self):

        # 1. Set a variable to a known value.
        # 2. Spawn a thread that will perform an interrupt after some number of seconds,
        # 3. Issue a long-running command - that spans during of interrupt thread wait time,
        # 4. Interrupt the kernel,
        # 5. Attempt to increment the variable, verify expected result.

        self.kernel.execute("var x = 123")
        original_value = int(self.kernel.execute("x"))  # This will only return the value.
        self.assertEqual(original_value, 123)

        # Start a thread that performs the interrupt.  This thread must wait long enough to issue
        # the next cell execution.
        self.kernel.start_interrupt_thread()

        # Build the code list to interrupt, in this case, its a sleep call.
        interrupted_code = list()
        interrupted_code.append('println("begin")\n')
        interrupted_code.append("Thread.sleep(60000)\n")
        interrupted_code.append('println("end")\n')
        interrupted_result = self.kernel.execute(interrupted_code)

        # Ensure the result indicates an interrupt occurred
        self.assertRegex(interrupted_result, "java.lang.InterruptedException")

        # Wait for thread to terminate - should be terminated already
        self.kernel.terminate_interrupt_thread()

        # Increment the pre-interrupt variable and ensure its value is correct
        self.kernel.execute("var y = x + 1")
        interrupted_value = int(self.kernel.execute("y"))  # This will only return the value.
        self.assertEqual(interrupted_value, 124)


class ScalaKernelBaseSparkTestCase(ScalaKernelBaseTestCase):
    """
    Scala related tests cases common to Spark (with Yarn the default RM)
    """

    def test_get_application_id(self):
        result = self.kernel.execute("sc.applicationId")
        self.assertRegex(result, self.get_expected_application_id())

    def test_get_spark_version(self):
        result = self.kernel.execute("sc.version")
        self.assertRegex(result, self.get_expected_spark_version())

    def test_get_resource_manager(self):
        result = self.kernel.execute('sc.getConf.get("spark.master")')
        self.assertRegex(result, self.get_expected_spark_master())

    def test_get_deploy_mode(self):
        result = self.kernel.execute('sc.getConf.get("spark.submit.deployMode")')
        self.assertRegex(result, self.get_expected_deploy_mode())


class TestScalaKernelLocal(unittest.TestCase, ScalaKernelBaseTestCase):
    SPARK_VERSION = os.getenv("SPARK_VERSION")
    DEFAULT_KERNELSPEC = f"spark_{SPARK_VERSION}_scala"
    KERNELSPEC = os.getenv(
        "SCALA_KERNEL_LOCAL_NAME", DEFAULT_KERNELSPEC
    )  # scala_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Scala kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down Scala kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestScalaKernelClient(unittest.TestCase, ScalaKernelBaseSparkTestCase):
    KERNELSPEC = os.getenv(
        "SCALA_KERNEL_CLIENT_NAME", "spark_scala_yarn_client"
    )  # spark_scala_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Scala kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down Scala kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestScalaKernelCluster(unittest.TestCase, ScalaKernelBaseSparkTestCase):
    KERNELSPEC = os.getenv(
        "SCALA_KERNEL_CLUSTER_NAME", "spark_scala_yarn_cluster"
    )  # spark_scala_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Scala kernel using {cls.KERNELSPEC} kernelspec")

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
