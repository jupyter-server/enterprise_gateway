# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for validation of client-selected kernel resources (GHSA-hchm-85c7-pr3j).

Clients choose some Kubernetes resources of their kernel pods through KERNEL_* values.
Enterprise Gateway must reject choices that let a kernel escape its pod or reach other
tenants, before any launch state (namespace, role binding, pod) exists.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from jupyter_client.ioloop.manager import AsyncIOLoopKernelManager
from jupyter_client.kernelspec import KernelSpec
from tornado import web

from enterprise_gateway.enterprisegatewayapp import EnterpriseGatewayApp
from enterprise_gateway.services.kernels.remotemanager import RemoteKernelManager
from enterprise_gateway.services.processproxies.container import validate_kernel_images

# Importing k8s.py loads the in-cluster config, and docker_swarm.py connects to Docker, at
# import time.
with patch("kubernetes.config.load_incluster_config"), patch(
    "kubernetes.config.load_kube_config"
), patch("docker.client.DockerClient.from_env"):
    from enterprise_gateway.services.processproxies import (
        docker_swarm,  # noqa: F401
        k8s,
    )
    from enterprise_gateway.services.processproxies.k8s import (
        KubernetesProcessProxy,
        validate_kernel_extra_spark_opts,
        validate_kernel_namespace,
        validate_kernel_service_account,
        validate_kernel_volumes,
    )

K8S_PROXY = "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy"
SPARK_OPERATOR_PROXY = (
    "enterprise_gateway.services.processproxies.spark_operator.SparkOperatorProcessProxy"
)
DOCKER_PROXY = "enterprise_gateway.services.processproxies.docker_swarm.DockerProcessProxy"
DEFAULT_VOLUME_TYPES = ["emptyDir", "persistentVolumeClaim", "configMap", "secret"]
DIGEST = "sha256:" + "a" * 64


def volumes(*items: dict) -> dict[str, str]:
    """Return a client env carrying ``items`` as KERNEL_VOLUMES (JSON, as clients send it)."""
    return {"KERNEL_VOLUMES": json.dumps(list(items))}


def rejection(env: dict[str, str], allowed=DEFAULT_VOLUME_TYPES) -> str:
    """Validate ``env`` expecting a 400 and return the error message."""
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_volumes(env, allowed)
    assert exc_info.value.status_code == 400
    return exc_info.value.log_message


# ---------------------------------------------------------------------------
# KERNEL_VOLUMES volume types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "volume",
    [
        {"name": "scratch", "emptyDir": {}},
        {"name": "data", "persistentVolumeClaim": {"claimName": "team-data"}},
        {"name": "conf", "configMap": {"name": "spark-conf"}},
        {"name": "creds", "secret": {"secretName": "db-creds"}},
    ],
)
def test_default_volume_types_accepted(volume):
    validate_kernel_volumes(volumes(volume), DEFAULT_VOLUME_TYPES)


@pytest.mark.parametrize(
    "volume_type, source",
    [
        ("hostPath", {"path": "/", "type": "Directory"}),  # node filesystem
        ("gitRepo", {"repository": "https://example.com/x.git"}),  # CVE-2024-10220
        ("nfs", {"server": "10.0.0.1", "path": "/"}),
        ("csi", {"driver": "secrets-store.csi.k8s.io"}),
        ("flexVolume", {"driver": "example/driver"}),
        ("projected", {"sources": []}),
        ("image", {"reference": "attacker/payload"}),
        ("ephemeral", {"volumeClaimTemplate": {}}),
        # Case variants must not slip past an exact-match allowlist (older API servers
        # decoded field names case-insensitively).
        ("HostPath", {"path": "/"}),
        ("emptydir", {}),
    ],
)
def test_other_volume_types_rejected_by_default(volume_type, source):
    message = rejection(volumes({"name": "vol", volume_type: source}))
    assert f"'{volume_type}'" in message
    assert "'vol'" in message
    assert "EG_ALLOWED_KERNEL_VOLUME_TYPES" in message


def test_rejection_lists_allowed_types():
    message = rejection(volumes({"name": "h", "hostPath": {"path": "/"}}))
    for volume_type in DEFAULT_VOLUME_TYPES:
        assert volume_type in message


def test_operator_can_allow_additional_type():
    validate_kernel_volumes(volumes({"name": "h", "hostPath": {"path": "/data"}}), ["hostPath"])


def test_wildcard_allows_any_type():
    validate_kernel_volumes(volumes({"name": "h", "hostPath": {"path": "/"}}), ["*"])


def test_kernelspec_override_is_comma_separated_string():
    """Kernelspec process-proxy config values are comma-separated strings."""
    validate_kernel_volumes(
        volumes({"name": "h", "hostPath": {"path": "/data"}}), "emptyDir, hostPath"
    )


def test_empty_allowlist_rejects_every_type():
    rejection(volumes({"name": "scratch", "emptyDir": {}}), allowed=[""])


def test_unsafe_type_name_not_echoed():
    """A type name that is not a plain identifier is never reflected in the error."""
    message = rejection(volumes({"name": "vol", "evil\nX-Injected: 1": {}}))
    assert "X-Injected" not in message


# ---------------------------------------------------------------------------
# KERNEL_VOLUMES structure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "volume",
    [
        {"name": "two", "emptyDir": {}, "hostPath": {"path": "/"}},  # hides a second source
        {"name": "none"},
    ],
)
def test_volume_must_define_exactly_one_source(volume):
    message = rejection(volumes(volume))
    assert "exactly one volume source" in message


@pytest.mark.parametrize(
    "volume",
    [
        {"emptyDir": {}},  # missing
        {"name": "Bad_Name", "emptyDir": {}},  # not a DNS-1123 label
        {"name": 7, "emptyDir": {}},
    ],
)
def test_volume_name_must_be_valid(volume):
    message = rejection(volumes(volume))
    assert "Bad_Name" not in message


@pytest.mark.parametrize(
    "raw_value",
    [
        "[{",  # malformed YAML
        "",  # parses to None
        '{"name": "a", "emptyDir": {}}',  # a mapping, not a list
        '["name: a"]',  # list of strings
    ],
)
def test_volumes_must_be_yaml_list_of_mappings(raw_value):
    message = rejection({"KERNEL_VOLUMES": raw_value})
    assert "KERNEL_VOLUMES" in message


def test_absent_volume_values_are_not_checked():
    validate_kernel_volumes({"KERNEL_USERNAME": "alice"}, [])


# ---------------------------------------------------------------------------
# KERNEL_VOLUME_MOUNTS
# ---------------------------------------------------------------------------


def test_volume_mount_with_all_supported_fields_accepted():
    mount = {
        "name": "data",
        "mountPath": "/data",
        "readOnly": True,
        "subPath": "team",
        "subPathExpr": "$(POD_NAME)",
        "mountPropagation": "None",
        "recursiveReadOnly": "Disabled",
    }
    validate_kernel_volumes({"KERNEL_VOLUME_MOUNTS": json.dumps([mount])}, DEFAULT_VOLUME_TYPES)


def test_volume_mount_unknown_field_rejected():
    mount = {"name": "data", "MountPath": "/data"}
    message = rejection({"KERNEL_VOLUME_MOUNTS": json.dumps([mount])})
    assert "'MountPath'" in message


def test_volume_mounts_must_be_list_of_mappings():
    message = rejection({"KERNEL_VOLUME_MOUNTS": "not-a-list"})
    assert "KERNEL_VOLUME_MOUNTS" in message


# ---------------------------------------------------------------------------
# KERNEL_IMAGE / KERNEL_EXECUTOR_IMAGE
# ---------------------------------------------------------------------------


def image_rejection(env: dict[str, str], allowed=(), configured=()) -> str:
    """Validate image values expecting a 400 and return the error message."""
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_images(env, allowed, configured)
    assert exc_info.value.status_code == 400
    return exc_info.value.log_message


@pytest.mark.parametrize(
    "image",
    [
        "python",
        "python:3.11",
        "elyra/kernel-py:3.3.0",
        "localhost:5000/kernel-py:dev",
        "registry.example.com:443/team/sub/kernel-py:v1.2_3",
        f"registry.example.com/team/kernel-py@{DIGEST}",
        f"elyra/kernel-py:3.3.0@{DIGEST}",
    ],
)
def test_any_well_formed_image_accepted_without_allowlist(image):
    validate_kernel_images({"KERNEL_IMAGE": image}, [], [])


@pytest.mark.parametrize(
    "image",
    [
        "Elyra/Kernel-py",  # repository paths are lowercase
        "elyra/kernel-py:",
        "-elyra/kernel-py",
        "elyra//kernel-py",
        "elyra/kernel-py:tag with space",
        "elyra/kernel-py@sha256:xyz",
        "elyra/kernel-py\nsecurityContext",
        "",
    ],
)
def test_malformed_image_rejected_without_echo(image):
    message = image_rejection({"KERNEL_IMAGE": image})
    assert "KERNEL_IMAGE" in message
    if image:
        assert image not in message


def test_executor_image_checked_too():
    message = image_rejection({"KERNEL_EXECUTOR_IMAGE": "Not/Valid"})
    assert "KERNEL_EXECUTOR_IMAGE" in message


@pytest.mark.parametrize(
    "image",
    [
        "elyra/kernel-py:3.3.0",
        "docker.io/elyra/kernel-spark-py",
        "index.docker.io/elyra/kernel-py",  # legacy Docker Hub domain
        f"elyra/kernel-r@{DIGEST}",
    ],
)
def test_allowlist_matches_docker_hub_namespace(image):
    validate_kernel_images({"KERNEL_IMAGE": image}, ["elyra/*"], [])


@pytest.mark.parametrize(
    "image",
    [
        "attacker/kernel-py:latest",
        "elyra.evil.com/kernel-py",  # registry whose name starts like the namespace
        "evil.com/elyra/kernel-py",  # same path on another registry
        "elyra",  # docker.io/library/elyra
    ],
)
def test_allowlist_rejects_other_images(image):
    message = image_rejection({"KERNEL_IMAGE": image}, allowed=["elyra/*"])
    assert f"'{image}'" in message
    assert "EG_ALLOWED_KERNEL_IMAGES" in message
    assert "elyra/*" in message


def test_allowlist_registry_port_is_part_of_the_match():
    validate_kernel_images(
        {"KERNEL_IMAGE": "registry.corp:5000/team/kernel:1"}, ["registry.corp:5000/*"], []
    )
    image_rejection({"KERNEL_IMAGE": "registry.corp/team/kernel:1"}, ["registry.corp:5000/*"])


def test_wildcard_in_registry_does_not_cross_slash():
    # A '*' in the registry part must not match a '/' and pick up a path that imitates the domain.
    pattern = ["*.example.com/*"]
    image_rejection({"KERNEL_IMAGE": "evil.com/x.example.com/y"}, pattern)
    image_rejection({"KERNEL_IMAGE": "x.example.com.evil.com/y"}, pattern)
    validate_kernel_images({"KERNEL_IMAGE": "reg.example.com/team/kernel:1"}, pattern, [])


def test_wildcard_registry_matches_real_registry_host():
    pattern = ["*.dkr.ecr.us-west-2.amazonaws.com/*"]
    validate_kernel_images(
        {"KERNEL_IMAGE": "123456789012.dkr.ecr.us-west-2.amazonaws.com/team/kernel:1"}, pattern, []
    )
    image_rejection({"KERNEL_IMAGE": "evil.com/kernel"}, pattern)


def test_docker_hub_wildcard_matches_all_namespaces():
    pattern = ["docker.io/*"]
    validate_kernel_images({"KERNEL_IMAGE": "elyra/kernel-py:3.3.0"}, pattern, [])
    validate_kernel_images({"KERNEL_IMAGE": "docker.io/elyra/kernel-py"}, pattern, [])
    validate_kernel_images({"KERNEL_IMAGE": "python:3.11"}, pattern, [])  # official image
    image_rejection({"KERNEL_IMAGE": "registry.corp/team/kernel"}, pattern)


def test_allowlist_ignores_tag_and_digest():
    allowed = ["elyra/kernel-py"]
    validate_kernel_images({"KERNEL_IMAGE": "elyra/kernel-py:anything"}, allowed, [])
    validate_kernel_images({"KERNEL_IMAGE": f"elyra/kernel-py@{DIGEST}"}, allowed, [])
    image_rejection({"KERNEL_IMAGE": "elyra/kernel-py-evil"}, allowed)


def test_official_image_pattern():
    validate_kernel_images({"KERNEL_IMAGE": "python:3.11"}, ["python"], [])


def test_image_kernelspec_override_is_comma_separated_string():
    validate_kernel_images({"KERNEL_IMAGE": "elyra/kernel-py"}, "registry.corp/*, elyra/*", [])


def test_wildcard_allows_any_well_formed_image():
    validate_kernel_images({"KERNEL_IMAGE": "attacker/kernel"}, ["*"], [])
    image_rejection({"KERNEL_IMAGE": "Not/Valid"}, allowed=["*"])


def test_operator_configured_image_always_allowed():
    """Clients that echo the kernelspec's own image keep working when an allowlist is set."""
    allowed, configured = ["registry.corp/*"], ["elyra/kernel-py:3.3.0"]
    validate_kernel_images({"KERNEL_IMAGE": "elyra/kernel-py:3.3.0"}, allowed, configured)
    image_rejection({"KERNEL_IMAGE": "elyra/kernel-py:other"}, allowed, configured)


# ---------------------------------------------------------------------------
# RemoteKernelManager.start_kernel hook
# ---------------------------------------------------------------------------


def make_kernel_manager(
    proxy_config: dict | None = None, inherited_envs=(), proxy_class: str = K8S_PROXY
) -> RemoteKernelManager:
    """Build a RemoteKernelManager for a container kernelspec without launching anything."""
    km = RemoteKernelManager(kernel_name="test")
    km._kernel_spec = KernelSpec(
        argv=["/bin/true"],
        display_name="Test",
        language="python",
        env={},
        metadata={"process_proxy": {"class_name": proxy_class, "config": proxy_config or {}}},
    )
    km.inherited_envs = list(inherited_envs)
    km.client_envs = []
    return km


@pytest.fixture
def launch():
    """Replace process-proxy construction and the real launch with mocks."""
    with patch.object(RemoteKernelManager, "_get_process_proxy") as get_proxy, patch.object(
        AsyncIOLoopKernelManager, "start_kernel", new=AsyncMock()
    ) as start:
        yield get_proxy, start


HOST_ROOT = {"name": "host-root", "hostPath": {"path": "/", "type": "Directory"}}


def test_rejected_volume_creates_no_process_proxy_and_no_launch(launch):
    get_proxy, start = launch
    km = make_kernel_manager()
    with pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(km.start_kernel(env=volumes(HOST_ROOT)))
    assert exc_info.value.status_code == 400
    get_proxy.assert_not_called()
    start.assert_not_awaited()


def test_allowed_volume_launches(launch):
    _, start = launch
    km = make_kernel_manager()
    asyncio.run(km.start_kernel(env=volumes({"name": "scratch", "emptyDir": {}})))
    start.assert_awaited_once()


def test_kernelspec_override_replaces_gateway_allowlist(launch):
    _, start = launch
    km = make_kernel_manager(proxy_config={"allowed_volume_types": "hostPath"})
    asyncio.run(km.start_kernel(env=volumes(HOST_ROOT)))
    start.assert_awaited_once()


def test_value_inherited_unchanged_from_gateway_env_is_trusted(launch):
    _, start = launch
    km = make_kernel_manager(inherited_envs=["KERNEL_VOLUMES"])
    env = volumes(HOST_ROOT)
    with patch.dict(os.environ, env):
        asyncio.run(km.start_kernel(env=env))
    start.assert_awaited_once()


def test_gateway_env_var_sets_allowlist(launch):
    _, start = launch
    with patch.dict(os.environ, {"EG_ALLOWED_KERNEL_VOLUME_TYPES": "emptyDir,hostPath"}):
        km = make_kernel_manager()
        asyncio.run(km.start_kernel(env=volumes(HOST_ROOT)))
    start.assert_awaited_once()


def test_app_setting_reaches_kernel_managers():
    app = EnterpriseGatewayApp(allowed_kernel_volume_types=["emptyDir", "hostPath"])
    app.init_configurables()
    km = RemoteKernelManager(parent=app.kernel_manager, kernel_name="test")
    assert km.allowed_kernel_volume_types == ["emptyDir", "hostPath"]


@pytest.mark.parametrize("proxy_class", [K8S_PROXY, DOCKER_PROXY])
def test_disallowed_image_rejected_before_launch(launch, proxy_class):
    get_proxy, start = launch
    km = make_kernel_manager(
        proxy_config={"image_name": "elyra/kernel-py:3.3.0", "allowed_images": "elyra/*"},
        proxy_class=proxy_class,
    )
    with pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(km.start_kernel(env={"KERNEL_IMAGE": "attacker/kernel:latest"}))
    assert exc_info.value.status_code == 400
    get_proxy.assert_not_called()
    start.assert_not_awaited()


def test_kernelspec_image_allowed_despite_gateway_allowlist(launch):
    _, start = launch
    km = make_kernel_manager(proxy_config={"image_name": "elyra/kernel-py:3.3.0"})
    km.allowed_kernel_images = ["registry.corp/*"]
    asyncio.run(km.start_kernel(env={"KERNEL_IMAGE": "elyra/kernel-py:3.3.0"}))
    start.assert_awaited_once()


def test_gateway_image_allowlist_enforced(launch):
    km = make_kernel_manager(proxy_config={"image_name": "elyra/kernel-py:3.3.0"})
    km.allowed_kernel_images = ["registry.corp/*"]
    with pytest.raises(web.HTTPError):
        asyncio.run(km.start_kernel(env={"KERNEL_IMAGE": "attacker/kernel:latest"}))


def test_image_allowlist_env_var(launch):
    with patch.dict(os.environ, {"EG_ALLOWED_KERNEL_IMAGES": "registry.corp/*"}):
        km = make_kernel_manager()
        with pytest.raises(web.HTTPError):
            asyncio.run(km.start_kernel(env={"KERNEL_IMAGE": "attacker/kernel:latest"}))


def test_image_allowlist_app_setting_reaches_kernel_managers():
    app = EnterpriseGatewayApp(allowed_kernel_images=["registry.corp/*"])
    app.init_configurables()
    km = RemoteKernelManager(parent=app.kernel_manager, kernel_name="test")
    assert km.allowed_kernel_images == ["registry.corp/*"]


# ---------------------------------------------------------------------------
# Docker launcher: KERNEL_GID is the primary group
# ---------------------------------------------------------------------------

LAUNCH_DOCKER = (
    Path(__file__).resolve().parents[2] / "etc/kernel-launchers/docker/scripts/launch_docker.py"
)


@pytest.fixture
def launch_docker():
    """Load the Docker kernel launcher script with a mock Docker client."""
    spec = importlib.util.spec_from_file_location("launch_docker", LAUNCH_DOCKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    docker_client = Mock()
    with patch.object(module.DockerClient, "from_env", return_value=docker_client):
        yield module, docker_client


def run_docker_launcher(module, env: dict[str, str]) -> None:
    kernel_env = {"KERNEL_IMAGE": "elyra/kernel-py:3.3.0", "PATH": "/usr/bin", **env}
    with patch.dict(os.environ, kernel_env, clear=True):
        module.launch_docker_kernel("kid", "0..0", "10.0.0.1:8877", "pubkey", "none", None)


@pytest.mark.parametrize("swarm", [False, True])
def test_docker_kernel_runs_with_kernel_gid_as_primary_group(launch_docker, swarm):
    """Without a group, Docker uses the image's passwd entry, or root for unknown UIDs."""
    module, docker_client = launch_docker
    module.swarm_mode = swarm
    run_docker_launcher(module, {"KERNEL_UID": "1000", "KERNEL_GID": "100"})
    launch = docker_client.services.create if swarm else docker_client.containers.run
    assert launch.call_args.kwargs["user"] == "1000:100"


def test_docker_kernel_without_gid_keeps_uid_only(launch_docker):
    module, docker_client = launch_docker
    module.swarm_mode = False
    run_docker_launcher(module, {"KERNEL_UID": "1000"})
    assert docker_client.containers.run.call_args.kwargs["user"] == "1000"


@pytest.mark.parametrize("swarm", [False, True])
@pytest.mark.parametrize("server_path", [None, "/usr/bin"])
def test_docker_kernel_uses_image_path(launch_docker, swarm, server_path):
    """The gateway does not forward its PATH to kernels; either way the image PATH is used."""
    module, docker_client = launch_docker
    module.swarm_mode = swarm
    kernel_env = {"KERNEL_IMAGE": "elyra/kernel-py:3.3.0"}
    if server_path is not None:
        kernel_env["PATH"] = server_path
    with patch.dict(os.environ, kernel_env, clear=True):
        module.launch_docker_kernel("kid", "0..0", "10.0.0.1:8877", "pubkey", "none", None)
    launch = docker_client.services.create if swarm else docker_client.containers.run
    env_kwarg = "env" if swarm else "environment"
    assert "PATH" not in launch.call_args.kwargs[env_kwarg]


# ---------------------------------------------------------------------------
# KERNEL_NAMESPACE / KERNEL_SERVICE_ACCOUNT_NAME
# ---------------------------------------------------------------------------

GATEWAY_NAMESPACE = "enterprise-gateway"


def namespace_rejection(namespace, allowed=(), managed=frozenset()) -> str:
    """Validate a client namespace expecting a 400 and return the error message."""
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_namespace(
            {"KERNEL_NAMESPACE": namespace}, allowed, GATEWAY_NAMESPACE, managed
        )
    assert exc_info.value.status_code == 400
    return exc_info.value.log_message


def test_namespace_not_checked_when_client_omits_it():
    validate_kernel_namespace({"KERNEL_USERNAME": "alice"}, [], GATEWAY_NAMESPACE, set())


def test_client_namespace_rejected_by_default():
    message = namespace_rejection("team-a")
    assert "'team-a'" in message
    assert "EG_ALLOWED_KERNEL_NAMESPACES" in message
    assert "omit KERNEL_NAMESPACE" in message


@pytest.mark.parametrize("namespace", ["team-a", "team-b2", "data-science"])
def test_allowlisted_namespace_accepted(namespace):
    validate_kernel_namespace(
        {"KERNEL_NAMESPACE": namespace}, ["team-*", "data-science"], GATEWAY_NAMESPACE, set()
    )


@pytest.mark.parametrize("namespace", ["teams", "data-science-x", "other"])
def test_namespace_outside_allowlist_rejected(namespace):
    namespace_rejection(namespace, allowed=["team-*", "data-science"])


def test_namespace_kernelspec_override_is_comma_separated_string():
    validate_kernel_namespace(
        {"KERNEL_NAMESPACE": "team-a"}, "data-science, team-*", GATEWAY_NAMESPACE, set()
    )


@pytest.mark.parametrize(
    "namespace", [GATEWAY_NAMESPACE, "kube-system", "kube-public", "kube-node-lease"]
)
def test_reserved_namespaces_rejected_even_with_wildcard(namespace):
    message = namespace_rejection(namespace, allowed=["*"])
    assert "reserved" in message


def test_namespace_managed_for_another_kernel_rejected_even_with_wildcard():
    message = namespace_rejection("alice-1234", allowed=["*"], managed={"alice-1234"})
    assert "another kernel" in message


@pytest.mark.parametrize("namespace", ["Team_A", "-team", "team.a", "a" * 64, ""])
def test_malformed_namespace_rejected_without_echo(namespace):
    message = namespace_rejection(namespace, allowed=["*"])
    assert "KERNEL_NAMESPACE" in message
    if namespace:
        assert namespace not in message


@pytest.mark.parametrize("account", ["default", "kernel-sa", "spark.operator-sa"])
def test_well_formed_service_account_accepted(account):
    # A non-default account is honored alongside a client namespace.
    validate_kernel_service_account(
        {"KERNEL_SERVICE_ACCOUNT_NAME": account, "KERNEL_NAMESPACE": "team-a"}, "default"
    )


@pytest.mark.parametrize("account", ["Kernel_SA", "a/b", "sa name", "", "-sa"])
def test_malformed_service_account_rejected_without_echo(account):
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_service_account({"KERNEL_SERVICE_ACCOUNT_NAME": account}, "default")
    assert exc_info.value.status_code == 400
    assert "KERNEL_SERVICE_ACCOUNT_NAME" in exc_info.value.log_message
    if account:
        assert account not in exc_info.value.log_message


def test_default_service_account_allowed_without_namespace():
    validate_kernel_service_account({"KERNEL_SERVICE_ACCOUNT_NAME": "default"}, "default")


def test_absent_service_account_not_checked():
    validate_kernel_service_account({"KERNEL_USERNAME": "alice"}, "default")


def test_client_service_account_without_namespace_rejected():
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_service_account(
            {"KERNEL_SERVICE_ACCOUNT_NAME": "enterprise-gateway-sa"}, "default"
        )
    assert exc_info.value.status_code == 400
    assert "KERNEL_NAMESPACE" in exc_info.value.log_message


def test_shared_namespace_service_account_hijack_rejected_before_launch(launch):
    """A client naming the gateway's own service account, with no namespace, is rejected."""
    get_proxy, start = launch
    km = make_kernel_manager()
    with pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(km.start_kernel(env={"KERNEL_SERVICE_ACCOUNT_NAME": "enterprise-gateway-sa"}))
    assert exc_info.value.status_code == 400
    get_proxy.assert_not_called()
    start.assert_not_awaited()


@pytest.mark.parametrize("proxy_class", [K8S_PROXY, SPARK_OPERATOR_PROXY])
def test_client_namespace_rejected_before_launch(launch, proxy_class):
    get_proxy, start = launch
    km = make_kernel_manager(proxy_class=proxy_class)
    with pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(km.start_kernel(env={"KERNEL_NAMESPACE": "team-a"}))
    assert exc_info.value.status_code == 400
    get_proxy.assert_not_called()
    start.assert_not_awaited()


def test_kernel_without_client_namespace_launches(launch):
    _, start = launch
    km = make_kernel_manager()
    asyncio.run(km.start_kernel(env={"KERNEL_USERNAME": "alice"}))
    start.assert_awaited_once()


def test_kernelspec_namespace_override(launch):
    _, start = launch
    km = make_kernel_manager(proxy_config={"allowed_namespaces": "team-*"})
    asyncio.run(km.start_kernel(env={"KERNEL_NAMESPACE": "team-a"}))
    start.assert_awaited_once()


def test_namespace_allowlist_env_var(launch):
    _, start = launch
    with patch.dict(os.environ, {"EG_ALLOWED_KERNEL_NAMESPACES": "team-*"}):
        km = make_kernel_manager()
        asyncio.run(km.start_kernel(env={"KERNEL_NAMESPACE": "team-a"}))
    start.assert_awaited_once()


def test_malformed_service_account_rejected_before_launch(launch):
    get_proxy, _ = launch
    km = make_kernel_manager()
    with pytest.raises(web.HTTPError):
        asyncio.run(km.start_kernel(env={"KERNEL_SERVICE_ACCOUNT_NAME": "Bad_SA"}))
    get_proxy.assert_not_called()


def test_namespace_allowlist_app_setting_reaches_kernel_managers():
    app = EnterpriseGatewayApp(allowed_kernel_namespaces=["team-*"])
    app.init_configurables()
    km = RemoteKernelManager(parent=app.kernel_manager, kernel_name="test")
    assert km.allowed_kernel_namespaces == ["team-*"]


# Namespaces Enterprise Gateway creates for kernels stay off-limits to clients until deleted.


@pytest.fixture
def k8s_proxy():
    """A KubernetesProcessProxy whose Kubernetes API calls go to mocks, with a fresh registry.

    Only the API entry points are mocked; request models such as V1Namespace stay real.
    """
    km = Mock()
    km.kernel_id = "kid"
    km.port_range = "0..0"
    km.restarting = False
    with patch(
        "enterprise_gateway.services.processproxies.processproxy.ResponseManager"
    ), patch.object(k8s.client, "CoreV1Api") as core_api, patch.object(
        k8s.client, "RbacAuthorizationV1Api"
    ), patch.object(
        k8s, "_managed_kernel_namespaces", set()
    ):
        api = core_api.return_value
        api.delete_namespaced_pod.return_value.status.phase = "Succeeded"
        api.delete_namespace.return_value.status = "Success"
        yield KubernetesProcessProxy(km, {})


def namespace_is_usable(namespace: str) -> bool:
    """Whether a client could launch into ``namespace`` when the operator allows any."""
    km = make_kernel_manager()
    try:
        KubernetesProcessProxy.validate_client_env(
            {"KERNEL_NAMESPACE": namespace}, {"allowed_namespaces": "*"}, km
        )
    except web.HTTPError:
        return False
    return True


def test_created_namespace_off_limits_until_deleted(k8s_proxy):
    k8s_proxy.kernel_pod_name = k8s_proxy.kernel_namespace = "alice-kid"
    k8s_proxy._create_kernel_namespace("default")
    assert not namespace_is_usable("alice-kid")

    k8s_proxy.terminate_container_resources()
    assert namespace_is_usable("alice-kid")


def test_namespace_kept_off_limits_across_restart(k8s_proxy):
    k8s_proxy.kernel_pod_name = k8s_proxy.kernel_namespace = "alice-kid"
    k8s_proxy._create_kernel_namespace("default")
    k8s_proxy.kernel_manager.restarting = True
    k8s_proxy.terminate_container_resources()  # restart keeps the namespace
    assert not namespace_is_usable("alice-kid")


def test_restored_kernel_namespace_off_limits(k8s_proxy):
    """Kernels loaded from persisted sessions register the namespace they own."""
    process_info = k8s_proxy.get_process_info()
    process_info.update(kernel_ns="bob-kid", delete_ns=True)
    k8s_proxy.load_process_info(process_info)
    assert not namespace_is_usable("bob-kid")


def test_client_supplied_namespace_not_registered(k8s_proxy):
    """Only namespaces Enterprise Gateway created are registered, not ones a client named."""
    process_info = k8s_proxy.get_process_info()
    process_info.update(kernel_ns="team-a", delete_ns=False)
    k8s_proxy.load_process_info(process_info)
    assert namespace_is_usable("team-a")


# ---------------------------------------------------------------------------
# Pod Security Admission labels on namespaces Enterprise Gateway creates
# ---------------------------------------------------------------------------

PSA = "pod-security.kubernetes.io"


def created_namespace_labels(proxy) -> dict[str, str]:
    """Create the kernel's namespace and return the labels sent to the Kubernetes API."""
    proxy.kernel_pod_name = "alice-kid"
    proxy._create_kernel_namespace("default")
    body = k8s.client.CoreV1Api.return_value.create_namespace.call_args.kwargs["body"]
    return body.metadata.labels


def test_created_namespace_enforces_baseline_pod_security(k8s_proxy):
    """Kernel code can create pods in its namespace; PSA keeps them off the node."""
    labels = created_namespace_labels(k8s_proxy)
    assert labels[f"{PSA}/enforce"] == "baseline"
    assert labels[f"{PSA}/warn"] == "baseline"
    assert labels[f"{PSA}/audit"] == "baseline"
    # The existing labels are kept.
    assert labels["app"] == "enterprise-gateway"
    assert labels["component"] == "kernel"
    assert labels["kernel_id"] == "kid"


def test_operator_can_change_pod_security_level(k8s_proxy):
    with patch.object(
        k8s, "kernel_namespace_pod_security_labels", k8s.pod_security_labels("restricted")
    ):
        labels = created_namespace_labels(k8s_proxy)
    assert labels[f"{PSA}/enforce"] == "restricted"


@pytest.mark.parametrize("level", ["privileged", "baseline", "restricted"])
def test_pod_security_labels_for_each_level(level):
    assert k8s.pod_security_labels(level) == {
        f"{PSA}/enforce": level,
        f"{PSA}/warn": level,
        f"{PSA}/audit": level,
    }


def test_empty_pod_security_level_adds_no_labels():
    """An empty level leaves the namespace to the cluster's default policy."""
    assert k8s.pod_security_labels("") == {}


def test_invalid_pod_security_level_fails_closed():
    with pytest.raises(ValueError) as exc_info:
        k8s.pod_security_labels("strict")
    assert "EG_KERNEL_NAMESPACE_POD_SECURITY" in str(exc_info.value)
    assert "baseline" in str(exc_info.value)


# ---------------------------------------------------------------------------
# KERNEL_EXTRA_SPARK_OPTS (Spark-on-Kubernetes)
# ---------------------------------------------------------------------------


def spark_opts_rejection(value, allowed=DEFAULT_VOLUME_TYPES) -> str:
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_extra_spark_opts({"KERNEL_EXTRA_SPARK_OPTS": value}, allowed)
    assert exc_info.value.status_code == 400
    return exc_info.value.log_message


def test_spark_opts_absent_not_checked():
    validate_kernel_extra_spark_opts({"KERNEL_USERNAME": "alice"}, DEFAULT_VOLUME_TYPES)


@pytest.mark.parametrize(
    "value",
    [
        "--conf spark.driver.memory=2g --conf spark.executor.memory=2g",
        "--conf spark.driver.cores=2",
        "--conf spark.kubernetes.driver.label.team=data",
        "--conf spark.kubernetes.driver.volumes.emptyDir.cache.mount.path=/cache",
        "--conf spark.kubernetes.driver.volumes.persistentVolumeClaim.d.mount.path=/d",
    ],
)
def test_benign_spark_opts_accepted(value):
    validate_kernel_extra_spark_opts({"KERNEL_EXTRA_SPARK_OPTS": value}, DEFAULT_VOLUME_TYPES)


@pytest.mark.parametrize(
    "value, needle",
    [
        ("--conf spark.kubernetes.namespace=kube-system", "spark.kubernetes.namespace"),
        (
            "--conf spark.kubernetes.driver.container.image=attacker/x",
            "spark.kubernetes.driver.container.image",
        ),
        (
            "--conf spark.kubernetes.executor.container.image=attacker/x",
            "spark.kubernetes.executor.container.image",
        ),
        (
            "--conf spark.kubernetes.authenticate.driver.serviceAccountName=enterprise-gateway-sa",
            "spark.kubernetes.authenticate",
        ),
        (
            "--conf spark.kubernetes.driver.podTemplateFile=/evil.yaml",
            "spark.kubernetes.driver.podTemplateFile",
        ),
        (
            "--conf spark.kubernetes.driver.secrets.creds=/secrets",
            "spark.kubernetes.driver.secrets",
        ),
    ],
)
def test_forbidden_spark_conf_keys_rejected(value, needle):
    message = spark_opts_rejection(value)
    assert needle in message


@pytest.mark.parametrize("flag", ["--master", "--deploy-mode", "--proxy-user"])
def test_forbidden_spark_flags_rejected(flag):
    message = spark_opts_rejection(f"{flag} value")
    assert flag in message


def test_hostpath_spark_volume_rejected_by_default():
    message = spark_opts_rejection(
        "--conf spark.kubernetes.driver.volumes.hostPath.h.mount.path=/host "
        "--conf spark.kubernetes.driver.volumes.hostPath.h.options.path=/"
    )
    assert "hostPath" in message


def test_hostpath_spark_volume_allowed_when_configured():
    validate_kernel_extra_spark_opts(
        {
            "KERNEL_EXTRA_SPARK_OPTS": "--conf spark.kubernetes.executor.volumes.hostPath.h.mount.path=/host"
        },
        ["hostPath"],
    )


def test_spark_volume_type_case_insensitive_match_still_enforced():
    # A lowercased hostpath must not slip past a case variation.
    spark_opts_rejection("--conf spark.kubernetes.driver.volumes.hostpath.h.mount.path=/host")


def test_forbidden_spark_conf_rejected_before_launch(launch):
    get_proxy, start = launch
    km = make_kernel_manager()
    with pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(
            km.start_kernel(
                env={"KERNEL_EXTRA_SPARK_OPTS": "--conf spark.kubernetes.namespace=kube-system"}
            )
        )
    assert exc_info.value.status_code == 400
    get_proxy.assert_not_called()
    start.assert_not_awaited()


def test_unparseable_spark_opts_rejected():
    spark_opts_rejection('--conf spark.driver.memory="2g')  # unbalanced quote


# ---------------------------------------------------------------------------
# A null kernelspec override inherits the gateway-wide setting
# ---------------------------------------------------------------------------


def test_null_allowed_images_override_inherits_gateway_list(launch):
    _, start = launch
    km = make_kernel_manager(proxy_config={"image_name": "elyra/kernel-py", "allowed_images": None})
    km.allowed_kernel_images = ["registry.corp/*"]
    with pytest.raises(web.HTTPError):  # inherits gateway list, which excludes attacker/x
        asyncio.run(km.start_kernel(env={"KERNEL_IMAGE": "attacker/x:latest"}))


def test_null_allowed_volume_types_override_inherits_gateway_default(launch):
    _, start = launch
    km = make_kernel_manager(proxy_config={"allowed_volume_types": None})
    # Inherits the gateway default (which includes emptyDir), so an emptyDir volume launches.
    asyncio.run(km.start_kernel(env=volumes({"name": "scratch", "emptyDir": {}})))
    start.assert_awaited_once()


def test_null_allowed_namespaces_override_inherits_gateway_list(launch):
    _, start = launch
    km = make_kernel_manager(proxy_config={"allowed_namespaces": None})
    km.allowed_kernel_namespaces = ["team-*"]
    asyncio.run(km.start_kernel(env={"KERNEL_NAMESPACE": "team-a"}))
    start.assert_awaited_once()


# ---------------------------------------------------------------------------
# Cross-replica namespace check via the Kubernetes API label
# ---------------------------------------------------------------------------


def _fake_namespace(labels):
    ns = Mock()
    ns.metadata.labels = labels
    return ns


def _patched_core_api(read_namespace):
    """Patch k8s.client.CoreV1Api so read_namespace is the given callable/mock."""
    core_api = Mock()
    core_api.return_value.read_namespace = read_namespace
    return patch.object(k8s.client, "CoreV1Api", core_api)


def test_namespace_with_kernel_id_label_rejected():
    """A namespace EG created for a kernel (on any replica) carries a kernel_id label."""
    read = Mock(return_value=_fake_namespace({"app": "enterprise-gateway", "kernel_id": "abc"}))
    with _patched_core_api(read), pytest.raises(web.HTTPError) as exc_info:
        k8s.reject_client_namespace_owned_by_eg({"KERNEL_NAMESPACE": "team-a"})
    assert exc_info.value.status_code == 400
    assert "team-a" in exc_info.value.log_message
    read.assert_called_once_with(name="team-a")


def test_operator_namespace_without_kernel_id_label_allowed():
    read = Mock(return_value=_fake_namespace({"app": "enterprise-gateway", "component": "kernel"}))
    with _patched_core_api(read):
        k8s.reject_client_namespace_owned_by_eg({"KERNEL_NAMESPACE": "team-a"})


def test_missing_namespace_not_rejected_by_label_check():
    read = Mock(side_effect=k8s.client.rest.ApiException(status=404))
    with _patched_core_api(read):
        k8s.reject_client_namespace_owned_by_eg({"KERNEL_NAMESPACE": "team-a"})


def test_label_check_skipped_without_client_namespace():
    read = Mock()
    with _patched_core_api(read):
        k8s.reject_client_namespace_owned_by_eg({"KERNEL_USERNAME": "alice"})
    read.assert_not_called()


def test_label_check_fails_open_on_api_error():
    """A transient API error does not block an allowlisted namespace."""
    read = Mock(side_effect=k8s.client.rest.ApiException(status=500))
    with _patched_core_api(read):
        k8s.reject_client_namespace_owned_by_eg({"KERNEL_NAMESPACE": "team-a"})


def test_cross_replica_namespace_rejected_before_launch(launch):
    get_proxy, start = launch
    km = make_kernel_manager()
    km.allowed_kernel_namespaces = ["team-*"]  # allowlisted, but EG created it on another replica
    read = Mock(return_value=_fake_namespace({"kernel_id": "abc"}))
    with _patched_core_api(read), pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(km.start_kernel(env={"KERNEL_NAMESPACE": "team-bob-123"}))
    assert exc_info.value.status_code == 400
    get_proxy.assert_not_called()
    start.assert_not_awaited()


# ---------------------------------------------------------------------------
# Image tags are ASCII (Docker grammar), not Unicode \w
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tag", ["é", "٣", "ñ", "３"])  # noqa: RUF001 - non-ASCII on purpose
def test_non_ascii_image_tag_rejected(tag):
    message = image_rejection({"KERNEL_IMAGE": f"elyra/kernel-py:{tag}"})
    assert "KERNEL_IMAGE" in message


@pytest.mark.parametrize("tag", ["3.11", "v1.2_3", "latest", "sha-abcdef"])
def test_ascii_image_tag_accepted(tag):
    validate_kernel_images({"KERNEL_IMAGE": f"elyra/kernel-py:{tag}"}, [], [])


# ---------------------------------------------------------------------------
# Restart re-validates the launch env before shutting the kernel down
# ---------------------------------------------------------------------------


def test_restart_rejects_now_disallowed_env_without_shutdown():
    """If an operator tightens the policy, a restart fails 400 and the kernel keeps running."""
    km = make_kernel_manager()
    km._launch_args = {"env": volumes(HOST_ROOT)}  # hostPath, no longer allowed
    km.process_proxy = Mock(spec=[])  # not a RemoteProcessProxy
    with patch.object(
        AsyncIOLoopKernelManager, "restart_kernel", new=AsyncMock()
    ) as base_restart, pytest.raises(web.HTTPError) as exc_info:
        asyncio.run(km.restart_kernel())
    assert exc_info.value.status_code == 400
    base_restart.assert_not_awaited()  # the running kernel was not shut down


def test_restart_with_still_valid_env_proceeds():
    km = make_kernel_manager()
    km._launch_args = {"env": {"KERNEL_USERNAME": "alice"}}
    km.process_proxy = Mock(spec=[])
    with patch.object(AsyncIOLoopKernelManager, "restart_kernel", new=AsyncMock()) as base_restart:
        asyncio.run(km.restart_kernel())
    base_restart.assert_awaited_once()
