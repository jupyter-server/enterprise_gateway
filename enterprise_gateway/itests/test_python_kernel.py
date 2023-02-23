import os
import unittest

from enterprise_gateway.client.gateway_client import GatewayClient

from .test_base import TestBase


class PythonKernelBaseTestCase(TestBase):
    """
    Python related test cases common to vanilla IPython kernels
    """

    def test_get_hostname(self):
        result, has_error = self.kernel.execute(
            "import subprocess; subprocess.check_output(['hostname'])"
        )
        self.assertEqual(has_error, False)
        self.assertRegex(result, self.get_expected_hostname())

    def test_hello_world(self):
        result, has_error = self.kernel.execute("print('Hello World')")
        self.assertEqual(has_error, False)
        self.assertRegex(result, "Hello World")

    def test_restart(self):
        # 1. Set a variable to a known value.
        # 2. Restart the kernel
        # 3. Attempt to increment the variable, verify an error was received (due to undefined variable)

        self.kernel.execute("x = 123")
        original_value, has_error = self.kernel.execute("print(x)")
        self.assertEqual(int(original_value), 123)
        self.assertEqual(has_error, False)

        self.assertTrue(self.kernel.restart())

        error_result, has_error = self.kernel.execute("y = x + 1")
        self.assertRegex(error_result, "NameError")
        self.assertEqual(has_error, True)

    def test_interrupt(self):
        # 1. Set a variable to a known value.
        # 2. Spawn a thread that will perform an interrupt after some number of seconds,
        # 3. Issue a long-running command - that spans during of interrupt thread wait time,
        # 4. Interrupt the kernel,
        # 5. Attempt to increment the variable, verify expected result.

        self.kernel.execute("x = 123")
        original_value, has_error = self.kernel.execute("print(x)")
        self.assertEqual(int(original_value), 123)
        self.assertEqual(has_error, False)

        # Start a thread that performs the interrupt.  This thread must wait long enough to issue
        # the next cell execution.
        self.kernel.start_interrupt_thread()

        # Build the code list to interrupt, in this case, its a sleep call.
        interrupted_code = []
        interrupted_code.append("import time\n")
        interrupted_code.append("print('begin')\n")
        interrupted_code.append("time.sleep(60)\n")
        interrupted_code.append("print('end')\n")

        interrupted_result, has_error = self.kernel.execute(interrupted_code)

        # Ensure the result indicates an interrupt occurred
        self.assertRegex(interrupted_result, "KeyboardInterrupt")
        self.assertEqual(has_error, True)

        # Wait for thread to terminate - should be terminated already
        self.kernel.terminate_interrupt_thread()

        # Increment the pre-interrupt variable and ensure its value is correct
        self.kernel.execute("y = x + 1")
        interrupted_value, has_error = self.kernel.execute("print(y)")
        self.assertEqual(int(interrupted_value), 124)
        self.assertEqual(has_error, False)

    def test_scope(self):
        # Ensure global variable is accessible in function.
        # See https://github.com/jupyter-server/enterprise_gateway/issues/687
        # Build the example code...
        scope_code = []
        scope_code.append("a = 42\n")
        scope_code.append("def scope():\n")
        scope_code.append("    return a\n")
        scope_code.append("\n")
        scope_code.append("scope()\n")
        result, has_error = self.kernel.execute(scope_code)
        self.assertEqual(result, str(42))
        self.assertEqual(has_error, False)


class PythonKernelBaseSparkTestCase(PythonKernelBaseTestCase):
    """
    Python related tests cases common to Spark on Yarn
    """

    def test_get_application_id(self):
        result, has_error = self.kernel.execute("sc.getConf().get('spark.app.id')")
        self.assertRegex(result, self.get_expected_application_id())
        self.assertEqual(has_error, False)

    def test_get_deploy_mode(self):
        result, has_error = self.kernel.execute("sc.getConf().get('spark.submit.deployMode')")
        self.assertRegex(result, self.get_expected_deploy_mode())
        self.assertEqual(has_error, False)

    def test_get_resource_manager(self):
        result, has_error = self.kernel.execute("sc.getConf().get('spark.master')")
        self.assertRegex(result, self.get_expected_spark_master())
        self.assertEqual(has_error, False)

    def test_get_spark_version(self):
        result, has_error = self.kernel.execute("sc.version")
        self.assertRegex(result, self.get_expected_spark_version())
        self.assertEqual(has_error, False)

    def test_run_pi_example(self):
        # Build the example code...
        pi_code = []
        pi_code.append("from random import random\n")
        pi_code.append("from operator import add\n")
        pi_code.append("partitions = 20\n")
        pi_code.append("n = 100000 * partitions\n")
        pi_code.append("def f(_):\n")
        pi_code.append("    x = random() * 2 - 1\n")
        pi_code.append("    y = random() * 2 - 1\n")
        pi_code.append("    return 1 if x ** 2 + y ** 2 <= 1 else 0\n")
        pi_code.append("count = sc.parallelize(range(1, n + 1), partitions).map(f).reduce(add)\n")
        pi_code.append('print("Pi is roughly %f" % (4.0 * count / n))\n')
        result, has_error = self.kernel.execute(pi_code)
        self.assertRegex(result, "Pi is roughly 3.14*")
        self.assertEqual(has_error, False)


class TestPythonKernelLocal(unittest.TestCase, PythonKernelBaseTestCase):
    KERNELSPEC = os.getenv("PYTHON_KERNEL_LOCAL_NAME", "python3")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Python kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down Python kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestPythonKernelDistributed(unittest.TestCase, PythonKernelBaseTestCase):
    KERNELSPEC = os.getenv(
        "PYTHON_KERNEL_DISTRIBUTED_NAME", "python_distributed"
    )  # python_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Python kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down Python kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestPythonKernelClient(unittest.TestCase, PythonKernelBaseSparkTestCase):
    KERNELSPEC = os.getenv(
        "PYTHON_KERNEL_CLIENT_NAME", "spark_python_yarn_client"
    )  # spark_python_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Python kernel using {cls.KERNELSPEC} kernelspec")

        # initialize environment
        cls.gatewayClient = GatewayClient()
        cls.kernel = cls.gatewayClient.start_kernel(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        print(f"\nShutting down Python kernel using {cls.KERNELSPEC} kernelspec")

        # shutdown environment
        cls.gatewayClient.shutdown_kernel(cls.kernel)


class TestPythonKernelCluster(unittest.TestCase, PythonKernelBaseSparkTestCase):
    KERNELSPEC = os.getenv(
        "PYTHON_KERNEL_CLUSTER_NAME", "spark_python_yarn_cluster"
    )  # spark_python_kubernetes for k8s

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print(f"\nStarting Python kernel using {cls.KERNELSPEC} kernelspec")

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
