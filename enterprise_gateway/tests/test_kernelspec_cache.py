# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for KernelSpecCache."""

import asyncio
import json
import os
import shutil
import sys

import jupyter_core.paths
import pytest
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel

from enterprise_gateway.services.kernelspecs import KernelSpecCache


# BEGIN - Remove once transition to jupyter_server occurs
def mkdir(tmp_path, *parts):
    path = tmp_path.joinpath(*parts)
    if not path.exists():
        path.mkdir(parents=True)
    return path


home_dir = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "home"))
data_dir = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "data"))
config_dir = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "config"))
runtime_dir = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "runtime"))
system_jupyter_path = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "share", "jupyter"))
env_jupyter_path = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "env", "share", "jupyter"))
system_config_path = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "etc", "jupyter"))
env_config_path = pytest.fixture(lambda tmp_path: mkdir(tmp_path, "env", "etc", "jupyter"))


@pytest.fixture
def environ(
    monkeypatch,
    tmp_path,
    home_dir,
    data_dir,
    config_dir,
    runtime_dir,
    system_jupyter_path,
    system_config_path,
    env_jupyter_path,
    env_config_path,
):
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(sys.path))
    monkeypatch.setenv("JUPYTER_NO_CONFIG", "1")
    monkeypatch.setenv("JUPYTER_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("JUPYTER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("JUPYTER_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setattr(jupyter_core.paths, "SYSTEM_JUPYTER_PATH", [str(system_jupyter_path)])
    monkeypatch.setattr(jupyter_core.paths, "ENV_JUPYTER_PATH", [str(env_jupyter_path)])
    monkeypatch.setattr(jupyter_core.paths, "SYSTEM_CONFIG_PATH", [str(system_config_path)])
    monkeypatch.setattr(jupyter_core.paths, "ENV_CONFIG_PATH", [str(env_config_path)])


# END - Remove once transition to jupyter_server occurs


kernelspec_json = {
    "argv": ["cat", "{connection_file}"],
    "display_name": "Test kernel: {kernel_name}",
}


def _install_kernelspec(kernels_dir, kernel_name):
    """install a sample kernel in a kernels directory"""
    kernelspec_dir = os.path.join(kernels_dir, kernel_name)
    os.makedirs(kernelspec_dir)
    json_file = os.path.join(kernelspec_dir, "kernel.json")
    named_json = kernelspec_json.copy()
    named_json["display_name"] = named_json["display_name"].format(kernel_name=kernel_name)
    with open(json_file, "w") as f:
        json.dump(named_json, f)
    return kernelspec_dir


def _modify_kernelspec(kernelspec_dir, kernel_name):
    json_file = os.path.join(kernelspec_dir, "kernel.json")
    kernel_json = kernelspec_json.copy()
    kernel_json["display_name"] = f"{kernel_name} modified!"
    with open(json_file, "w") as f:
        json.dump(kernel_json, f)


kernelspec_location = pytest.fixture(lambda data_dir: mkdir(data_dir, "kernels"))
other_kernelspec_location = pytest.fixture(
    lambda env_jupyter_path: mkdir(env_jupyter_path, "kernels")
)


@pytest.fixture
def setup_kernelspecs(environ, kernelspec_location):
    # Only populate factory info
    _install_kernelspec(str(kernelspec_location), "test1")
    _install_kernelspec(str(kernelspec_location), "test2")
    _install_kernelspec(str(kernelspec_location), "test3")


@pytest.fixture
def kernel_spec_manager(environ, setup_kernelspecs):
    yield KernelSpecManager(ensure_native_kernel=False)


@pytest.fixture
def kernel_spec_cache(is_enabled, kernel_spec_manager):
    kspec_cache = KernelSpecCache.instance(
        kernel_spec_manager=kernel_spec_manager, cache_enabled=is_enabled
    )
    yield kspec_cache
    kspec_cache = None
    KernelSpecCache.clear_instance()


@pytest.fixture(params=[False, True])  # Add types as needed
def is_enabled(request):
    return request.param


async def tests_get_all_specs(kernel_spec_cache):
    kspecs = await kernel_spec_cache.get_all_specs()
    assert len(kspecs) == 3


async def tests_get_named_spec(kernel_spec_cache):
    kspec = await kernel_spec_cache.get_kernel_spec("test2")
    assert kspec.display_name == "Test kernel: test2"


async def tests_get_modified_spec(kernel_spec_cache):
    kspec = await kernel_spec_cache.get_kernel_spec("test2")
    assert kspec.display_name == "Test kernel: test2"

    # Modify entry
    _modify_kernelspec(kspec.resource_dir, "test2")
    await asyncio.sleep(0.5)  # sleep for a half-second to allow cache to update item
    kspec = await kernel_spec_cache.get_kernel_spec("test2")
    assert kspec.display_name == "test2 modified!"


async def tests_add_spec(kernel_spec_cache, kernelspec_location, other_kernelspec_location):
    assert len(kernel_spec_cache.observed_dirs) == (1 if kernel_spec_cache.cache_enabled else 0)
    assert (
        str(kernelspec_location) in kernel_spec_cache.observed_dirs
        if kernel_spec_cache.cache_enabled
        else True
    )

    _install_kernelspec(str(other_kernelspec_location), "added")
    kspec = await kernel_spec_cache.get_kernel_spec("added")

    # Ensure new location has been added to observed_dirs
    assert len(kernel_spec_cache.observed_dirs) == (2 if kernel_spec_cache.cache_enabled else 0)
    assert (
        str(other_kernelspec_location) in kernel_spec_cache.observed_dirs
        if kernel_spec_cache.cache_enabled
        else True
    )

    assert kspec.display_name == "Test kernel: added"
    assert kernel_spec_cache.cache_misses == (1 if kernel_spec_cache.cache_enabled else 0)

    # Add another to an existing observed directory, no cache miss here
    _install_kernelspec(str(kernelspec_location), "added2")
    await asyncio.sleep(
        0.5
    )  # sleep for a half-second to allow cache to add item (no cache miss in this case)
    kspec = await kernel_spec_cache.get_kernel_spec("added2")

    assert kspec.display_name == "Test kernel: added2"
    assert kernel_spec_cache.cache_misses == (1 if kernel_spec_cache.cache_enabled else 0)


async def tests_remove_spec(kernel_spec_cache):
    kspec = await kernel_spec_cache.get_kernel_spec("test2")
    assert kspec.display_name == "Test kernel: test2"

    assert kernel_spec_cache.cache_misses == 0
    shutil.rmtree(kspec.resource_dir)
    await asyncio.sleep(0.5)  # sleep for a half-second to allow cache to remove item
    with pytest.raises(NoSuchKernel):
        await kernel_spec_cache.get_kernel_spec("test2")

    assert kernel_spec_cache.cache_misses == (1 if kernel_spec_cache.cache_enabled else 0)


async def tests_get_missing(kernel_spec_cache):
    with pytest.raises(NoSuchKernel):
        await kernel_spec_cache.get_kernel_spec("missing")

    assert kernel_spec_cache.cache_misses == (1 if kernel_spec_cache.cache_enabled else 0)
