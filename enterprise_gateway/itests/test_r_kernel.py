import unittest
import os
from enterprise_gateway.client.gateway_client import GatewayClient


class RKernelBaseTestCase(object):
    """
    R related test cases common to vanilla IRKernel kernels
    """

    def test_hello_world(self):
        result = self.kernel.execute('print("Hello World", quote = FALSE)')
        self.assertRegexpMatches(result, 'Hello World')

    def test_restart(self):

        # 1. Set a variable to a known value.
        # 2. Restart the kernel
        # 3. Attempt to increment the variable, verify an error was received (due to undefined variable)

        self.kernel.execute("x = 123")
        original_value = int(self.kernel.execute("write(x,stdout())"))  # This will only return the value.
        self.assertEquals(original_value, 123)

        self.assertTrue(self.kernel.restart())

        error_result = self.kernel.execute("y = x + 1")
        self.assertRegexpMatches(error_result, 'Error in eval')

    def test_interrupt(self):

        # 1. Set a variable to a known value.
        # 2. Spawn a thread that will perform an interrupt after some number of seconds,
        # 3. Issue a long-running command - that spans during of interrupt thread wait time,
        # 4. Interrupt the kernel,
        # 5. Attempt to increment the variable, verify expected result.

        self.kernel.execute("x = 123")
        original_value = int(self.kernel.execute("write(x,stdout())"))  # This will only return the value.
        self.assertEquals(original_value, 123)

        # Start a thread that performs the interrupt.  This thread must wait long enough to issue
        # the next cell execution.
        self.kernel.start_interrupt_thread()

        # Build the code list to interrupt, in this case, its a sleep call.
        interrupted_code = list()
        interrupted_code.append('write("begin",stdout())\n')
        interrupted_code.append("Sys.sleep(30)\n")
        interrupted_code.append('write("end",stdout())\n')
        interrupted_result = self.kernel.execute(interrupted_code)

        # Ensure the result indicates an interrupt occurred
        self.assertEquals(interrupted_result.strip(), 'begin')

        # Wait for thread to terminate - should be terminated already
        self.kernel.terminate_interrupt_thread()

        # Increment the pre-interrupt variable and ensure its value is correct
        self.kernel.execute("y = x + 1")
        interrupted_value = int(self.kernel.execute("write(y,stdout())"))  # This will only return the value.
        self.assertEquals(interrupted_value, 124)


class RKernelBaseYarnTestCase(RKernelBaseTestCase):
    """
    R related tests cases common to Spark on Yarn
    """

    def test_get_application_id(self):
        result = self.kernel.execute('SparkR:::callJMethod(SparkR:::callJMethod(sc, "sc"), "applicationId")')
        self.assertRegexpMatches(result, 'application_')

    def test_get_spark_version(self):
        result = self.kernel.execute("sparkR.version()")
        self.assertRegexpMatches(result, '2.3')

    def test_get_resource_manager(self):
        result = self.kernel.execute('unlist(sparkR.conf("spark.master"))')
        self.assertRegexpMatches(result, 'yarn')

    def test_get_deploy_mode(self):
        result = self.kernel.execute('unlist(sparkR.conf("spark.submit.deployMode"))')
        self.assertRegexpMatches(result, '(cluster|client)')

    def test_get_host_address(self):
        result = self.kernel.execute('unlist(sparkR.conf("spark.driver.host"))')
        self.assertRegexpMatches(result, 'itest')


class TestRKernelLocal(unittest.TestCase, RKernelBaseTestCase):
    KERNELSPEC = os.getenv("R_KERNEL_LOCAL_NAME", "ir")

    @classmethod
    def setUpClass(cls):
        super(TestRKernelLocal, cls).setUpClass()
        print('>>>')
        print('Starting R kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestRKernelLocal, cls).tearDownClass()
        print('Shutting down R kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestRKernelClient(unittest.TestCase, RKernelBaseYarnTestCase):
    KERNELSPEC = os.getenv("R_KERNEL_CLIENT_NAME", "spark_R_yarn_client")

    @classmethod
    def setUpClass(cls):
        super(TestRKernelClient, cls).setUpClass()
        print('>>>')
        print('Starting R kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestRKernelClient, cls).tearDownClass()
        print('Shutting down R kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestRKernelCluster(unittest.TestCase, RKernelBaseYarnTestCase):
    KERNELSPEC = os.getenv("R_KERNEL_CLUSTER_NAME", "spark_R_yarn_cluster")

    @classmethod
    def setUpClass(cls):
        super(TestRKernelCluster, cls).setUpClass()
        print('>>>')
        print('Starting Python kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestRKernelCluster, cls).tearDownClass()
        print('Shutting down Python kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


if __name__ == '__main__':
    unittest.main()