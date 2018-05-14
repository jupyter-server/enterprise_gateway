import unittest
import re

from enterprise_gateway.itests.kernel_client import KernelLauncher


class ScalaKernelBaseTestCase(object):
    """
    R Related test cases where there is a concrete
    test class for each available kernelspec for R kernels

    IPython related kernelspec
    - spark_R_yarn_client
    - spark_R_yarn_cluster
    """

    def test_hello_world(self):
        result = self.kernel.execute('println("Hello World")')
        assert re.search('Hello World', result)

    def test_get_application_id(self):
        result = self.kernel.execute('sc.applicationId')
        assert re.search('application_', result)

    def test_get_spark_version(self):
        result = self.kernel.execute("sc.version")
        assert re.search('2.1', result)

    def test_get_resource_manager(self):
        result = self.kernel.execute('sc.getConf.get("spark.master")')
        assert re.search('yarn', result)

    def test_get_deploy_mode(self):
        result = self.kernel.execute('sc.getConf.get("spark.submit.deployMode")')
        assert re.findall('(cluster|client)', result)

    def test_get_host_address(self):
        result = self.kernel.execute('sc.getConf.get("spark.driver.host")')
        assert re.findall('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', result)


class TestScalaKernelClient(unittest.TestCase, ScalaKernelBaseTestCase):
    KERNELSPEC = "spark_scala_yarn_client"

    @classmethod
    def setUpClass(cls):
        super(TestScalaKernelClient, cls).setUpClass()
        print('>>>')
        print('Starting Scala kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.launcher = KernelLauncher()
        cls.kernel = cls.launcher.launch(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestScalaKernelClient, cls).tearDownClass()
        print('Shutting down Scala kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.launcher.shutdown(cls.kernel.kernel_id)


class TestScalaKernelCluster(unittest.TestCase, ScalaKernelBaseTestCase):
    KERNELSPEC = "spark_scala_yarn_cluster"

    @classmethod
    def setUpClass(cls):
        super(TestScalaKernelCluster, cls).setUpClass()
        print('>>>')
        print('Starting Python kernel using {} kernelspec'.format(cls.KERNELSPEC))

        # initialize environment
        cls.launcher = KernelLauncher()
        cls.kernel = cls.launcher.launch(cls.KERNELSPEC)

    @classmethod
    def tearDownClass(cls):
        super(TestScalaKernelCluster, cls).tearDownClass()
        print('Shutting down Python kernel using {} kernelspec'.format(cls.KERNELSPEC))
        # shutdown environment
        cls.launcher.shutdown(cls.kernel.kernel_id)


if __name__ == '__main__':
    unittest.main()