import os

expected_hostname = os.getenv("ITEST_HOSTNAME_PREFIX", "") + "*"  # use ${KERNEL_USERNAME} on k8s
expected_application_id = os.getenv(
    "EXPECTED_APPLICATION_ID", "application_*"
)  # use 'spark-application-*' on k8s
expected_spark_version = os.getenv("EXPECTED_SPARK_VERSION", "3.2.*")  # use '2.4.*' on k8s
expected_spark_master = os.getenv("EXPECTED_SPARK_MASTER", "yarn")  # use 'k8s:*' on k8s
expected_deploy_mode = os.getenv("EXPECTED_DEPLOY_MODE", "(cluster|client)")  # use 'client' on k8s


class TestBase:
    def get_expected_application_id(self):
        return expected_application_id

    def get_expected_spark_version(self):
        return expected_spark_version

    def get_expected_spark_master(self):
        return expected_spark_master

    def get_expected_deploy_mode(self):
        return expected_deploy_mode

    def get_expected_hostname(self):
        return expected_hostname
