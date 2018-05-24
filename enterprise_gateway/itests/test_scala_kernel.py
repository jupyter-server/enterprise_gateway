import unittest
import os
from enterprise_gateway.client.gateway_client import GatewayClient


class ScalaKernelBaseTestCase(object):
    """
    Scala related test cases common to vanilla Scala kernels
    """

    def test_hello_world(self):
        result = self.kernel.execute('println("Hello World")')
        self.assertRegexpMatches(result, 'Hello World')

    def test_restart(self):

        # 1. Set a variable to a known value.
        # 2. Restart the kernel
        # 3. Attempt to increment the variable, verify an error was received (due to undefined variable)

        self.kernel.execute("var x = 123")
        original_value = int(self.kernel.execute("x"))  # This will only return the value.
        self.assertEquals(original_value, 123)

        self.assertTrue(self.kernel.restart())

        error_result = self.kernel.execute("var y = x + 1")
        self.assertRegexpMatches(error_result, 'Compile Error')

    def test_interrupt(self):

        # 1. Set a variable to a known value.
        # 2. Spawn a thread that will perform an interrupt after some number of seconds,
        # 3. Issue a long-running command - that spans during of interrupt thread wait time,
        # 4. Interrupt the kernel,
        # 5. Attempt to increment the variable, verify expected result.

        self.kernel.execute("var x = 123")
        original_value = int(self.kernel.execute("x"))  # This will only return the value.
        self.assertEquals(original_value, 123)

        # Start a thread that performs the interrupt.  This thread must wait long enough to issue
        # the next cell execution.
        self.kernel.start_interrupt_thread()

        # Build the code list to interrupt, in this case, its a sleep call.
        interrupted_code = list()
        interrupted_code.append('println("begin")\n')
        interrupted_code.append("Thread.sleep(30000)\n")
        interrupted_code.append('println("end")\n')
        interrupted_result = self.kernel.execute(interrupted_code)

        # Ensure the result indicates an interrupt occurred
        self.assertRegexpMatches(interrupted_result, 'java.lang.InterruptedException')

        # Wait for thread to terminate - should be terminated already
        self.kernel.terminate_interrupt_thread()

        # Increment the pre-interrupt variable and ensure its value is correct
        self.kernel.execute("var y = x + 1")
        interrupted_value = int(self.kernel.execute("y"))  # This will only return the value.
        self.assertEquals(interrupted_value, 124)


class ScalaKernelBaseYarnTestCase(ScalaKernelBaseTestCase):
    """
    Scala related tests cases common to Spark on Yarn
    """

    def test_get_application_id(self):
        result = self.kernel.execute('sc.applicationId')
        self.assertRegexpMatches(result, 'application_')

    def test_get_spark_version(self):
        result = self.kernel.execute("sc.version")
        self.assertRegexpMatches(result, '2.1')

    def test_get_resource_manager(self):
        result = self.kernel.execute('sc.getConf.get("spark.master")')
        self.assertRegexpMatches(result, 'yarn')

    def test_get_deploy_mode(self):
        result = self.kernel.execute('sc.getConf.get("spark.submit.deployMode")')
        self.assertRegexpMatches(result, '(cluster|client)')

    def test_get_host_address(self):
        result = self.kernel.execute('sc.getConf.get("spark.driver.host")')
        self.assertRegexpMatches(result, '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')


class TestScalaKernelLocal(unittest.TestCase, ScalaKernelBaseTestCase):
    KERNELSPEC = os.getenv("SCALA_KERNEL_LOCAL_NAME", "spark_2.1_scala")

    @classmethod
    def setUpClass(cls):
        super(TestScalaKernelLocal, cls).setUpClass()
        print('>>>')
        print('Starting Scala kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestScalaKernelLocal, cls).tearDownClass()
        print('Shutting down Scala kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)



class TestScalaKernelClient(unittest.TestCase, ScalaKernelBaseYarnTestCase):
    KERNELSPEC = os.getenv("SCALA_KERNEL_CLIENT_NAME", "spark_scala_yarn_client")

    @classmethod
    def setUpClass(cls):
        super(TestScalaKernelClient, cls).setUpClass()
        print('>>>')
        print('Starting Scala kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestScalaKernelClient, cls).tearDownClass()
        print('Shutting down Scala kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestScalaKernelCluster(unittest.TestCase, ScalaKernelBaseYarnTestCase):
    KERNELSPEC = os.getenv("SCALA_KERNEL_CLUSTER_NAME", "spark_scala_yarn_cluster")

    @classmethod
    def setUpClass(cls):
        super(TestScalaKernelCluster, cls).setUpClass()
        print('>>>')
        print('Starting Python kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestScalaKernelCluster, cls).tearDownClass()
        print('Shutting down Python kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


if __name__ == '__main__':
    unittest.main()