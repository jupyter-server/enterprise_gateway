# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for the Ray operator kernel templates (KubeRay RayCluster custom resources)."""

import importlib.util
import os
import stat
import subprocess

import pytest
import yaml

OPERATOR_SCRIPTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "..", "..", "etc", "kernel-launchers", "operators", "scripts"
    )
)


def _load_operator_launcher():
    """Import launch_custom_resource.py so templates render with the launcher's own Jinja setup."""
    spec = importlib.util.spec_from_file_location(
        "eg_operator_launcher", os.path.join(OPERATOR_SCRIPTS_DIR, "launch_custom_resource.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = _load_operator_launcher()

# RayOperatorProcessProxy sets KERNEL_CRD_GROUP=ray.io and KERNEL_CRD_VERSION=v1alpha1, so the
# launcher renders this template.
RAY_TEMPLATE = "ray.io-v1alpha1"


def _keywords(**overrides) -> dict:
    """Keywords shaped like the ones launch_custom_resource_kernel() builds for a Ray kernel."""
    keywords = {
        "eg_port_range": "40000..41000",
        "eg_public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA",
        "eg_response_address": "10.0.0.1:8877",
        "kernel_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "kernel_name": "ray_python_operator",
        "spark_context_initialization_mode": "none",
        "kernel_crd_group": "ray.io",
        "kernel_crd_version": "v1alpha1",
        "kernel_crd_plural": "rayclusters",
        "kernel_namespace": "enterprise-gateway",
        "kernel_resource_name": "ray-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "kernel_service_account_name": "default",
        "kernel_image": "elyra/kernel-ray-py:dev",
    }
    keywords.update(overrides)
    return keywords


def _render(template: str, **overrides) -> dict:
    """Render a Ray template and parse it; fail the test if the result is not valid YAML."""
    rendered = launcher.generate_kernel_custom_resource_yaml(template, _keywords(**overrides))
    try:
        return yaml.safe_load(rendered)
    except yaml.YAMLError as err:
        pytest.fail(f"{template} rendered invalid YAML: {err}")


def _head_container(cluster: dict, name: str = "ray-head") -> dict:
    containers = cluster["spec"]["headGroupSpec"]["template"]["spec"]["containers"]
    return next(c for c in containers if c["name"] == name)


def _walk(node):
    """Yield every mapping key and scalar value of a parsed YAML document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)
    else:
        yield node


# ---------------------------------------------------------------------------
# Head node probes
# ---------------------------------------------------------------------------

# /api/cluster_status as served by a rayproject/ray:2.58.0 head (`ray start --head`), abridged.
# It reports autoscaler state; nothing in it says "ALIVE", however healthy the head is.
RAY_2_58_CLUSTER_STATUS = (
    '{"result": true, "msg": "Got cluster status.", "data": {"autoscalingStatus": '
    '"Cluster status: 0 nodes\\n - ResourceUsage: 0.0/8.0 CPU, 0.0 GiB/12.61 GiB memory", '
    '"autoscalingError": null, "clusterStatus": {"autoscalerReport": {"activeNodes": '
    '{"node993314143439a1205f54faf8261fabfc1d85621953fd88539c67e568": 1}}}}}'
)

# Stub wget for a Ray head: the dashboard (port 8265) serves the endpoints the probes query.
FAKE_WGET = """#!/bin/sh
for arg in "$@"; do url="$arg"; done
case "$url" in
  http://localhost:8265/*) [ "$FAKE_DASHBOARD" = up ] || exit 4 ;;
  *) exit 4 ;;
esac
case "$url" in
  */api/gcs_healthz) [ "$FAKE_GCS" = healthy ] || exit 8; printf success ;;
  */api/cluster_status) printf '%s' "$FAKE_CLUSTER_STATUS" ;;
esac
"""

# Stub nc: `nc -z <host> 6379` succeeds while the GCS port is open.
FAKE_NC = """#!/bin/sh
[ "$1" = -z ] && [ "$3" = 6379 ] && [ "$FAKE_GCS" != down ]
"""

HEAD_STATES = [
    pytest.param({"FAKE_GCS": "healthy", "FAKE_DASHBOARD": "up"}, True, id="healthy-head"),
    pytest.param({"FAKE_GCS": "down", "FAKE_DASHBOARD": "up"}, False, id="gcs-port-closed"),
    pytest.param({"FAKE_GCS": "unhealthy", "FAKE_DASHBOARD": "up"}, False, id="gcs-unhealthy"),
    pytest.param({"FAKE_GCS": "healthy", "FAKE_DASHBOARD": "down"}, False, id="dashboard-down"),
]


@pytest.fixture
def fake_ray_head_tools(tmp_path):
    """Directory holding stub nc/wget binaries that mimic a Ray head's ports and dashboard."""
    for name, body in (("wget", FAKE_WGET), ("nc", FAKE_NC)):
        tool = tmp_path / name
        tool.write_text(body)
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return tmp_path


@pytest.mark.parametrize("probe", ["startupProbe", "readinessProbe"])
@pytest.mark.parametrize("head_state, expect_ready", HEAD_STATES)
def test_head_probe_reports_gcs_health(fake_ray_head_tools, probe, head_state, expect_ready):
    command = _head_container(_render(RAY_TEMPLATE))[probe]["exec"]["command"]
    env = {
        **os.environ,
        "PATH": f"{fake_ray_head_tools}{os.pathsep}{os.environ['PATH']}",
        "FAKE_CLUSTER_STATUS": RAY_2_58_CLUSTER_STATUS,
        **head_state,
    }
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=30, check=False
    )
    assert (result.returncode == 0) is expect_ready, result.stderr


# ---------------------------------------------------------------------------
# YAML injection through interpolated values
# ---------------------------------------------------------------------------

# Breaks out of a quoted or plain YAML scalar if interpolated raw.
INJECTION_PAYLOAD = 'x"\ninjected: true\n#'

# Values interpolated into the Ray templates. KERNEL_* ones can come from the client.
RAY_STRING_KEYWORDS = [
    "kernel_resource_name",
    "kernel_id",
    "kernel_service_account_name",
    "kernel_image",
    "kernel_head_num_cpu_limit",
    "kernel_head_memory_limit",
    "kernel_head_num_cpu_request",
    "kernel_head_memory_request",
    "kernel_cpu_worker_num_cpu_limit",
    "kernel_cpu_worker_num_memory_limit",
    "kernel_cpu_worker_num_cpu_request",
    "kernel_cpu_worker_num_memory_request",
    "kernel_serve_url",
    "kernel_build_url",
    "eg_response_address",
    "eg_port_range",
    "eg_public_key",
]


@pytest.mark.parametrize("keyword", RAY_STRING_KEYWORDS)
def test_value_with_yaml_syntax_stays_a_single_string(keyword):
    values = list(_walk(_render(RAY_TEMPLATE, **{keyword: INJECTION_PAYLOAD})))
    assert "injected" not in values
    assert INJECTION_PAYLOAD in values


# Interpolated only on commented-out template lines (GPU worker group, nodeSelectors).
# Jinja renders those lines too, so a raw newline in the value would escape the YAML comment.
COMMENTED_LINE_KEYWORDS = [
    "kernel_cpu_instance_type",
    "kernel_gpu_instance_type",
    "kernel_num_gpu_worker",
    "kernel_gpu_worker_num_cpu_limit",
    "kernel_gpu_worker_num_cpu_request",
    "kernel_gpu_worker_num_gpu",
    "kernel_gpu_worker_num_memory_limit",
    "kernel_gpu_worker_num_memory_request",
]


@pytest.mark.parametrize("keyword", COMMENTED_LINE_KEYWORDS)
def test_value_on_commented_line_cannot_escape_the_comment(keyword):
    assert "injected" not in list(_walk(_render(RAY_TEMPLATE, **{keyword: INJECTION_PAYLOAD})))


def test_worker_max_replicas_cannot_inject_yaml():
    cluster = _render(RAY_TEMPLATE, kernel_num_cpu_worker=INJECTION_PAYLOAD)
    assert "injected" not in list(_walk(cluster))
    assert isinstance(cluster["spec"]["workerGroupSpecs"][0]["maxReplicas"], int)


def test_worker_max_replicas_honors_client_value():
    cluster = _render(RAY_TEMPLATE, kernel_num_cpu_worker="3")
    assert cluster["spec"]["workerGroupSpecs"][0]["maxReplicas"] == 3
