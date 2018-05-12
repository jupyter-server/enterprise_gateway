from .elyra_client import ElyraClient
import pytest
import re
from .notebook_body import NBCodeEntity


@pytest.fixture(autouse=True)
def setup(host, username):
    print("\nSetting up the Environment")

    # Create a new notebook object with the path to a notebook
    nb_entity = NBCodeEntity("../notebooks/Python_Client1.ipynb", host)
    # Tell gateway to create a new kernel and return and save kernel id
    nb_entity.kernel_id = ElyraClient.create_kernel(nb_entity.kernel_spec_name,
                                                    username, ElyraClient.get_api_endpoint(host))
    yield nb_entity
    print("\nTearing down the Environment and Cleaning Up")
    ElyraClient.delete_kernel(nb_entity.kernel_id, ElyraClient.get_api_endpoint(host))


def test_hello_world(setup):
    assert setup.run_cell(1) == "Hello World"


def test_get_application_id(setup):
    assert re.match("application*", setup.run_cell(2))


def test_get_spark_version(setup):
    assert re.match("u'2.2.*", setup.run_cell(3))


def test_get_resource(setup):
    assert setup.run_cell(4) == "u'yarn'"


def test_get_deploy_mode(setup):
    assert setup.run_cell(5) == "u'client'"


def test_get_host_address(setup):
    assert re.match("^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                    setup.run_cell(6))
