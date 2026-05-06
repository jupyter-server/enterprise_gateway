# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for YAML injection vulnerability fix (GHSA-cfw7-6c5v-2wjq)."""

import os
import unittest

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "etc",
    "kernel-launchers",
    "kubernetes",
    "scripts",
)

OPERATOR_TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "etc",
    "kernel-launchers",
    "operators",
    "scripts",
)

YAML_PARSED_KERNEL_VARS = {"KERNEL_VOLUME_MOUNTS", "KERNEL_VOLUMES"}

ALLOWED_K8S_KINDS = {
    "Pod",
    "Secret",
    "PersistentVolumeClaim",
    "PersistentVolume",
    "Service",
    "ConfigMap",
}


def yaml_safe_str(value):
    """Escape a value for safe inclusion in a YAML template."""
    if isinstance(value, str):
        return yaml.dump(value, default_style='"', width=10000).strip()
    if isinstance(value, (dict, list)):
        return yaml.dump(value, default_flow_style=True, width=10000).strip()
    # yaml.dump appends a document-end marker ("...\n") for scalars; strip it
    return yaml.dump(value, width=10000).replace("\n...", "").strip()


def _build_keywords(env_overrides: dict) -> dict:
    """Build a keywords dict from env_overrides using the fixed parsing logic."""
    keywords = {}
    for name, value in env_overrides.items():
        if name.startswith("KERNEL_"):
            if name in YAML_PARSED_KERNEL_VARS:
                parsed = yaml.safe_load(value)
                if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
                    keywords[name.lower()] = parsed
            else:
                keywords[name.lower()] = value
    return keywords


def _render_pod_template(keywords: dict) -> str:
    """Render the kernel-pod.yaml.j2 template with the yaml_safe filter."""
    j_env = Environment(
        loader=FileSystemLoader(os.path.normpath(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape(
            disabled_extensions=("j2", "yaml"),
            default_for_string=True,
            default=True,
        ),
    )
    j_env.filters["yaml_safe"] = yaml_safe_str
    return j_env.get_template("/kernel-pod.yaml.j2").render(**keywords)


def _base_env() -> dict:
    return {
        "KERNEL_POD_NAME": "test-pod",
        "KERNEL_NAMESPACE": "default",
        "KERNEL_ID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "KERNEL_IMAGE": "elyra/kernel-py:3.2.3",
        "KERNEL_SERVICE_ACCOUNT_NAME": "default",
        "KERNEL_UID": "1000",
        "KERNEL_GID": "100",
    }


class TestYamlSafeStrFilter(unittest.TestCase):
    """Test the yaml_safe_str Jinja2 filter."""

    def test_normal_string(self):
        result = yaml_safe_str("/home/jovyan")
        self.assertEqual(result, '"/home/jovyan"')

    def test_string_with_quotes(self):
        result = yaml_safe_str('hello "world"')
        self.assertIn("hello", result)
        parsed = yaml.safe_load(f"key: {result}")
        self.assertEqual(parsed["key"], 'hello "world"')

    def test_string_with_newlines_escaped(self):
        result = yaml_safe_str("line1\nline2\nline3")
        self.assertNotIn("\n", result.strip('"'))
        parsed = yaml.safe_load(f"key: {result}")
        self.assertEqual(parsed["key"], "line1\nline2\nline3")

    def test_document_boundary_escaped(self):
        result = yaml_safe_str("before\n---\nafter")
        parsed_docs = list(yaml.safe_load_all(f"key: {result}"))
        self.assertEqual(len(parsed_docs), 1)
        self.assertEqual(parsed_docs[0]["key"], "before\n---\nafter")

    def test_end_of_document_marker_escaped(self):
        result = yaml_safe_str("before\n...\nafter")
        parsed = yaml.safe_load(f"key: {result}")
        self.assertIn("...", parsed["key"])

    def test_none_serialized_as_yaml_null(self):
        result = yaml_safe_str(None)
        self.assertEqual(result, "null")
        parsed = yaml.safe_load(f"key: {result}")
        self.assertIsNone(parsed["key"])

    def test_bool_serialized_as_yaml_bool(self):
        self.assertEqual(yaml_safe_str(True), "true")
        self.assertEqual(yaml_safe_str(False), "false")
        parsed_true = yaml.safe_load(f"key: {yaml_safe_str(True)}")
        parsed_false = yaml.safe_load(f"key: {yaml_safe_str(False)}")
        self.assertIs(parsed_true["key"], True)
        self.assertIs(parsed_false["key"], False)

    def test_numeric_serialized_correctly(self):
        self.assertEqual(yaml_safe_str(1000), "1000")
        self.assertEqual(yaml_safe_str(3.14), "3.14")
        parsed_int = yaml.safe_load(f"key: {yaml_safe_str(1000)}")
        parsed_float = yaml.safe_load(f"key: {yaml_safe_str(3.14)}")
        self.assertEqual(parsed_int["key"], 1000)
        self.assertAlmostEqual(parsed_float["key"], 3.14)

    def test_dict_rendered_as_flow_mapping(self):
        result = yaml_safe_str({"name": "data", "mountPath": "/data"})
        parsed = yaml.safe_load(f"- {result}")
        self.assertEqual(parsed[0]["name"], "data")
        self.assertEqual(parsed[0]["mountPath"], "/data")

    def test_empty_string(self):
        result = yaml_safe_str("")
        parsed = yaml.safe_load(f"key: {result}")
        self.assertEqual(parsed["key"], "")

    def test_image_name_with_tag(self):
        result = yaml_safe_str("registry.example.com/org/image:v1.2.3")
        parsed = yaml.safe_load(f"key: {result}")
        self.assertEqual(parsed["key"], "registry.example.com/org/image:v1.2.3")


class TestEnvVarParsing(unittest.TestCase):
    """Test that env var parsing correctly distinguishes scalar vs structured vars."""

    def test_scalar_vars_remain_strings(self):
        env = {"KERNEL_IMAGE": "nginx:latest", "KERNEL_UID": "1000"}
        keywords = _build_keywords(env)
        self.assertEqual(keywords["kernel_image"], "nginx:latest")
        self.assertIsInstance(keywords["kernel_image"], str)
        self.assertEqual(keywords["kernel_uid"], "1000")
        self.assertIsInstance(keywords["kernel_uid"], str)

    def test_volume_mounts_parsed_as_list(self):
        env = {
            "KERNEL_VOLUME_MOUNTS": '[{"name": "data", "mountPath": "/data"}]',
        }
        keywords = _build_keywords(env)
        self.assertIsInstance(keywords["kernel_volume_mounts"], list)
        self.assertEqual(keywords["kernel_volume_mounts"][0]["name"], "data")

    def test_volumes_parsed_as_list(self):
        env = {
            "KERNEL_VOLUMES": '[{"name": "data", "emptyDir": {}}]',
        }
        keywords = _build_keywords(env)
        self.assertIsInstance(keywords["kernel_volumes"], list)

    def test_non_list_volume_rejected(self):
        env = {"KERNEL_VOLUME_MOUNTS": "not-a-list"}
        keywords = _build_keywords(env)
        self.assertNotIn("kernel_volume_mounts", keywords)

    def test_list_of_strings_volume_rejected(self):
        """List of strings (not dicts) should be rejected to prevent injection via loop items."""
        env = {"KERNEL_VOLUME_MOUNTS": '["name: data\\nmountPath: /data"]'}
        keywords = _build_keywords(env)
        self.assertNotIn("kernel_volume_mounts", keywords)

    def test_mixed_list_volume_rejected(self):
        """List containing both dicts and strings should be rejected."""
        env = {"KERNEL_VOLUME_MOUNTS": '[{"name": "ok"}, "injected\\nstring"]'}
        keywords = _build_keywords(env)
        self.assertNotIn("kernel_volume_mounts", keywords)

    def test_yaml_safe_load_not_applied_to_scalars(self):
        env = {"KERNEL_WORKING_DIR": '"injected\\nvalue"'}
        keywords = _build_keywords(env)
        self.assertEqual(keywords["kernel_working_dir"], '"injected\\nvalue"')
        self.assertNotIn("\n", keywords["kernel_working_dir"])


class TestSecurityContextInjection(unittest.TestCase):
    """Test that securityContext injection via KERNEL_WORKING_DIR is blocked."""

    def test_security_context_not_overridden(self):
        env = _base_env()
        env["KERNEL_WORKING_DIR"] = (
            '"/tmp\\"\\n\\nsecurityContext:\\n  runAsUser: 0\\n  runAsGroup: 0\\n  fsGroup: 100\\n"'
        )
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        docs = list(yaml.safe_load_all(rendered))

        self.assertEqual(len(docs), 1)
        sc = docs[0]["spec"]["securityContext"]
        self.assertEqual(sc["runAsUser"], 1000)
        self.assertEqual(sc["runAsGroup"], 100)

    def test_injection_via_kernel_image(self):
        env = _base_env()
        env["KERNEL_IMAGE"] = 'nginx"\nsecurityContext:\n  runAsUser: 0'
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        docs = list(yaml.safe_load_all(rendered))

        self.assertEqual(len(docs), 1)
        sc = docs[0]["spec"]["securityContext"]
        self.assertEqual(sc["runAsUser"], 1000)

    def test_injection_via_kernel_namespace(self):
        env = _base_env()
        env["KERNEL_NAMESPACE"] = 'default"\nsecurityContext:\n  runAsUser: 0'
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        docs = list(yaml.safe_load_all(rendered))

        self.assertEqual(len(docs), 1)
        sc = docs[0]["spec"]["securityContext"]
        self.assertEqual(sc["runAsUser"], 1000)

    def test_injection_via_volume_mounts_string_list_blocked_at_l1(self):
        """L1: list-of-strings in KERNEL_VOLUME_MOUNTS is rejected during parsing."""
        env = _base_env()
        env["KERNEL_VOLUME_MOUNTS"] = (
            '["{name: data, mountPath: /data}\\n  securityContext:\\n    runAsUser: 0"]'
        )
        keywords = _build_keywords(env)
        self.assertNotIn("kernel_volume_mounts", keywords)

    def test_injection_via_volume_mounts_blocked_at_l2(self):
        """L2: even if a string slips into volume_mounts, yaml_safe filter escapes it."""
        env = _base_env()
        keywords = _build_keywords(env)
        keywords["kernel_volume_mounts"] = [
            "{name: data, mountPath: /data}\n  securityContext:\n    runAsUser: 0"
        ]
        rendered = _render_pod_template(keywords)
        docs = list(yaml.safe_load_all(rendered))

        self.assertEqual(len(docs), 1)
        sc = docs[0]["spec"]["securityContext"]
        self.assertEqual(sc["runAsUser"], 1000)
        env["KERNEL_WORKING_DIR"] = (
            '/tmp\n...\n---\napiVersion: v1\nkind: Pod\nmetadata:\n'  # noqa: S108
            '  name: injected-pod\nspec:\n  containers:\n'
            '  - name: evil\n    image: nginx\n    securityContext:\n'
            '      privileged: true\n...\n'
        )
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        docs = [d for d in yaml.safe_load_all(rendered) if d is not None]

        self.assertEqual(len(docs), 1, "Injected document should not create extra YAML documents")
        self.assertEqual(docs[0]["kind"], "Pod")
        self.assertEqual(docs[0]["metadata"]["name"], "test-pod")

    def test_all_rendered_kinds_are_allowed(self):
        env = _base_env()
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        docs = [d for d in yaml.safe_load_all(rendered) if d is not None]

        for doc in docs:
            self.assertIn(
                doc.get("kind"),
                ALLOWED_K8S_KINDS,
                f"Unexpected kind: {doc.get('kind')}",
            )

    def test_duplicate_pod_kind_detected(self):
        """L3: if an attacker somehow injected a second Pod, document count validation catches it."""
        multi_pod_yaml = (
            "apiVersion: v1\nkind: Pod\nmetadata:\n  name: legit\n"
            "---\n"
            "apiVersion: v1\nkind: Pod\nmetadata:\n  name: evil\n"
        )
        docs = list(yaml.safe_load_all(multi_pod_yaml))
        kind_counts: dict[str, int] = {}
        for doc in docs:
            if doc:
                kind = doc.get("kind")
                kind_counts[kind] = kind_counts.get(kind, 0) + 1

        self.assertEqual(kind_counts.get("Pod"), 2)
        self.assertGreater(kind_counts["Pod"], 1, "Should detect duplicate Pod documents")


class TestNormalOperation(unittest.TestCase):
    """Test that the fix preserves normal kernel launch functionality."""

    def test_basic_pod_renders_correctly(self):
        env = _base_env()
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        docs = list(yaml.safe_load_all(rendered))

        self.assertEqual(len(docs), 1)
        pod = docs[0]
        self.assertEqual(pod["kind"], "Pod")
        self.assertEqual(pod["metadata"]["name"], "test-pod")
        self.assertEqual(pod["metadata"]["namespace"], "default")
        self.assertEqual(pod["spec"]["containers"][0]["image"], "elyra/kernel-py:3.2.3")
        self.assertEqual(pod["spec"]["serviceAccountName"], "default")

    def test_working_dir_set_correctly(self):
        env = _base_env()
        env["KERNEL_WORKING_DIR"] = "/home/jovyan/work"
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        pod = yaml.safe_load(rendered)

        self.assertEqual(pod["spec"]["containers"][0]["workingDir"], "/home/jovyan/work")

    def test_resource_limits_rendered(self):
        env = _base_env()
        env["KERNEL_CPUS"] = "500m"
        env["KERNEL_MEMORY"] = "1Gi"
        env["KERNEL_CPUS_LIMIT"] = "1"
        env["KERNEL_MEMORY_LIMIT"] = "2Gi"
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        pod = yaml.safe_load(rendered)

        resources = pod["spec"]["containers"][0]["resources"]
        self.assertEqual(resources["requests"]["cpu"], "500m")
        self.assertEqual(resources["requests"]["memory"], "1Gi")
        self.assertEqual(resources["limits"]["cpu"], "1")
        self.assertEqual(resources["limits"]["memory"], "2Gi")

    def test_security_context_with_uid_gid(self):
        env = _base_env()
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        pod = yaml.safe_load(rendered)

        sc = pod["spec"]["securityContext"]
        self.assertEqual(sc["runAsUser"], 1000)
        self.assertEqual(sc["runAsGroup"], 100)
        self.assertEqual(sc["fsGroup"], 100)

    def test_volume_mounts_rendered(self):
        env = _base_env()
        env["KERNEL_VOLUME_MOUNTS"] = '[{"name": "data-vol", "mountPath": "/data"}]'
        env["KERNEL_VOLUMES"] = '[{"name": "data-vol", "emptyDir": {}}]'
        keywords = _build_keywords(env)
        rendered = _render_pod_template(keywords)
        pod = yaml.safe_load(rendered)

        mounts = pod["spec"]["containers"][0]["volumeMounts"]
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0]["name"], "data-vol")

        volumes = pod["spec"]["volumes"]
        self.assertEqual(len(volumes), 1)
        self.assertEqual(volumes[0]["name"], "data-vol")


class TestSparkOperatorTemplate(unittest.TestCase):
    """Test that the Spark operator template is also protected."""

    def _render_operator_template(self, keywords: dict) -> str:
        j_env = Environment(
            loader=FileSystemLoader(os.path.normpath(OPERATOR_TEMPLATE_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=select_autoescape(
                disabled_extensions=("j2", "yaml"),
                default_for_string=True,
                default=True,
            ),
        )
        j_env.filters["yaml_safe"] = yaml_safe_str
        return j_env.get_template("/sparkoperator.k8s.io-v1beta2.yaml.j2").render(**keywords)

    def test_injection_via_kernel_image_blocked(self):
        keywords = {
            "kernel_resource_name": "test-spark",
            "kernel_image": 'nginx\nmalicious:\n  key: value',
            "kernel_id": "test-id",
            "spark_context_initialization_mode": "none",
            "eg_response_address": "1.2.3.4:8080",
            "eg_port_range": "0..0",
            "eg_public_key": "testkey",
            "kernel_service_account_name": "default",
            "kernel_executor_image": "elyra/kernel-py:3.2.3",
        }
        rendered = self._render_operator_template(keywords)
        doc = yaml.safe_load(rendered)

        self.assertEqual(doc["kind"], "SparkApplication")
        self.assertIn("\n", doc["spec"]["image"])
        self.assertNotIn("malicious", doc)

    def test_normal_spark_app_renders(self):
        keywords = {
            "kernel_resource_name": "test-spark",
            "kernel_image": "elyra/kernel-spark-py:3.2.3",
            "kernel_id": "test-id-123",
            "spark_context_initialization_mode": "lazy",
            "eg_response_address": "10.0.0.1:8080",
            "eg_port_range": "10000..11000",
            "eg_public_key": "abc123",
            "kernel_service_account_name": "spark-sa",
            "kernel_executor_image": "elyra/kernel-spark-py:3.2.3",
        }
        rendered = self._render_operator_template(keywords)
        doc = yaml.safe_load(rendered)

        self.assertEqual(doc["kind"], "SparkApplication")
        self.assertEqual(doc["metadata"]["name"], "test-spark")
        self.assertEqual(doc["spec"]["image"], "elyra/kernel-spark-py:3.2.3")
        self.assertEqual(doc["spec"]["driver"]["serviceAccount"], "spark-sa")


if __name__ == "__main__":
    unittest.main()
