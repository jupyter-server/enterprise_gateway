def pytest_addoption(parser):
    parser.addoption("--host", action="store", default="localhost:8888")
    parser.addoption("--username", action="store", default="elyra")
    parser.addoption("--impersonation", action="store", default="false")


def pytest_generate_tests(metafunc):
    # This is called for every test. Only get/set command line arguments
    # if the argument is specified in the list of test "fixturenames".
    if "host" in metafunc.fixturenames:
        metafunc.parametrize("host", [metafunc.config.option.host])
    if "username" in metafunc.fixturenames:
        metafunc.parametrize("username", [metafunc.config.option.username])
    if "impersonation" in metafunc.fixturenames:
        metafunc.parametrize("impersonation", [metafunc.config.option.impersonation])
