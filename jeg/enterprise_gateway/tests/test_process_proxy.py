# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for Kubernetes process proxy security fixes."""

import unittest
from unittest.mock import Mock, patch

# Mock Kubernetes configuration before importing the module
with patch('kubernetes.config.load_incluster_config'), patch('kubernetes.config.load_kube_config'):
    from enterprise_gateway.services.processproxies.k8s import KubernetesProcessProxy


class TestKubernetesProcessProxy(unittest.TestCase):
    """Test secure template substitution in Kubernetes process proxy."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_kernel_manager = Mock()
        self.mock_kernel_manager.get_kernel_username.return_value = "testuser"
        self.mock_kernel_manager.port_range = "0..0"  # Mock port range

        # Mock proxy config
        self.proxy_config = {"kernel_id": "test-kernel-id", "kernel_name": "python3"}

        # Mock KernelSessionManager methods
        with patch(
            'enterprise_gateway.services.processproxies.k8s.KernelSessionManager'
        ) as mock_session_manager:
            mock_session_manager.get_kernel_username.return_value = "testuser"
            self.proxy = KubernetesProcessProxy(self.mock_kernel_manager, self.proxy_config)
            self.proxy.kernel_id = "test-kernel-id"

    def test_valid_template_substitution(self):
        """Test valid template variable substitution."""
        test_cases = [
            # Basic variable substitution
            ("{{ kernel_id }}", {"kernel_id": "test-123"}, "test-123"),
            # Multiple variables
            (
                "{{ kernel_namespace }}-{{ kernel_id }}",
                {"kernel_namespace": "default", "kernel_id": "test-123"},
                "default-test-123",
            ),
            # Variables with underscores
            ("{{ kernel_image_pull_policy }}", {"kernel_image_pull_policy": "Always"}, "Always"),
            # Whitespace handling
            ("{{   kernel_id   }}", {"kernel_id": "test-123"}, "test-123"),
        ]

        for template, variables, expected in test_cases:
            with self.subTest(template=template):
                result = self.proxy._safe_template_substitute(template, variables)
                self.assertEqual(result, expected)

    def test_missing_variables_fallback(self):
        # Test the full pod name determination process
        kwargs = {
            "env": {
                "KERNEL_POD_NAME": "{{ missing_var }}",
                "KERNEL_NAMESPACE": "production",
            }
        }

        with patch.object(self.proxy, 'log'), patch(
            'enterprise_gateway.services.processproxies.k8s.KernelSessionManager'
        ) as mock_session_manager:
            mock_session_manager.get_kernel_username.return_value = "testuser"
            result = self.proxy._determine_kernel_pod_name(**kwargs)
            # Should fall back to default naming: kernel_username + "-" + kernel_id
            self.assertEqual(result, "testuser-test-kernel-id")

    def test_malicious_template_injection_prevention(self):
        """Test prevention of malicious template injection attacks."""
        malicious_templates = [
            # Python code execution attempts
            "{{ ''.__class__.__mro__[1].__subclasses__()[104].__init__.__globals__['sys'].exit() }}",
            "{{ __import__('os').system('rm -rf /') }}",
            "{{ exec('print(\"pwned\")') }}",
            "{{ eval('1+1') }}",
            # Attribute access attempts
            "{{ kernel_id.__class__ }}",
            "{{ kernel_id.__dict__ }}",
            "{{ kernel_id.__globals__ }}",
            # Function calls
            "{{ range(10) }}",
            "{{ len(kernel_id) }}",
            "{{ str.upper(kernel_id) }}",
            # Jinja2 filters and expressions
            "{{ kernel_id|upper }}",
            "{{ kernel_id + '_suffix' }}",
            "{{ 1 + 1 }}",
            # Complex expressions
            "{{ kernel_id if kernel_id else 'default' }}",
            "{{ kernel_id[:5] }}",
        ]

        variables = {"kernel_id": "test-123"}

        for malicious_template in malicious_templates:
            with self.subTest(template=malicious_template), patch.object(
                self.proxy, 'log'
            ) as mock_log:
                result = self.proxy._safe_template_substitute(malicious_template, variables)
                # All malicious templates should be treated as invalid and return None
                self.assertIsNone(result)
                mock_log.warning.assert_called_once()
                # Should warn about unsupported expressions
                self.assertIn("Invalid template syntax", mock_log.warning.call_args[0][0])

    def test_pod_name_determination_with_templates(self):
        """Test complete pod name determination with template processing."""
        kwargs = {
            "env": {
                "KERNEL_POD_NAME": "{{ kernel_namespace }}-{{ kernel_id }}",
                "KERNEL_NAMESPACE": "production",
                "KERNEL_IMAGE": "python:3.9",
            }
        }

        with patch.object(self.proxy, 'log'):
            result = self.proxy._determine_kernel_pod_name(**kwargs)
            # Should get processed and DNS-normalized
            self.assertEqual(result, "production-test-kernel-id")

    def test_pod_name_determination_with_malicious_template(self):
        """Test pod name determination with malicious template falls back to default."""
        kwargs = {
            "env": {
                "KERNEL_POD_NAME": "{{ __import__('os').system('evil') }}",
                "KERNEL_NAMESPACE": "production",
            }
        }

        with patch.object(self.proxy, 'log'), patch(
            'enterprise_gateway.services.processproxies.k8s.KernelSessionManager'
        ) as mock_session_manager:
            mock_session_manager.get_kernel_username.return_value = "testuser"
            result = self.proxy._determine_kernel_pod_name(**kwargs)
            # Should fall back to default naming
            self.assertEqual(result, "testuser-test-kernel-id")

    def test_pod_name_determination_with_missing_variables(self):
        """Test pod name determination with missing variables falls back to default."""
        kwargs = {
            "env": {
                "KERNEL_POD_NAME": "{{ missing_var }}-{{ kernel_id }}",
                "KERNEL_NAMESPACE": "production",
            }
        }

        with patch.object(self.proxy, 'log'), patch(
            'enterprise_gateway.services.processproxies.k8s.KernelSessionManager'
        ) as mock_session_manager:
            mock_session_manager.get_kernel_username.return_value = "testuser"
            result = self.proxy._determine_kernel_pod_name(**kwargs)
            # Should fall back to default naming
            self.assertEqual(result, "testuser-test-kernel-id")

    def test_pod_name_without_template(self):
        """Test pod name determination without template syntax."""
        kwargs = {"env": {"KERNEL_POD_NAME": "static-pod-name", "KERNEL_NAMESPACE": "production"}}

        with patch.object(self.proxy, 'log'):
            result = self.proxy._determine_kernel_pod_name(**kwargs)
            # Should use as-is and DNS-normalize
            self.assertEqual(result, "static-pod-name")

    def test_pod_name_dns_normalization(self):
        """Test DNS name normalization of pod names."""
        kwargs = {
            "env": {
                "KERNEL_POD_NAME": "{{ kernel_namespace }}_{{ kernel_id }}",
                "KERNEL_NAMESPACE": "Test-Namespace",
                "KERNEL_IMAGE": "python:3.9",
            }
        }

        with patch.object(self.proxy, 'log'):
            result = self.proxy._determine_kernel_pod_name(**kwargs)
            # Should be DNS-normalized (lowercase, dashes only)
            self.assertEqual(result, "test-namespace-test-kernel-id")

    def test_regex_pattern_validation(self):
        """Test that only valid variable names are matched by regex."""
        valid_vars = [
            "kernel_id",
            "kernel_namespace",
            "kernel_image_pull_policy",
            "a",
            "var123",
            "KERNEL_ID",
        ]

        # Variables that should be blocked by the regex pattern
        invalid_vars = [
            "123invalid",  # starts with number
            "invalid-var",  # contains dash
            "invalid.var",  # contains dot
            "invalid var",  # contains space
            "invalid@var",  # contains special char
            "_private_var",  # starts with underscore (security risk)
            "__class__",  # magic method (security risk)
            "__dict__",  # magic method (security risk)
            "__globals__",  # magic method (security risk)
        ]

        variables = {var: "value" for var in valid_vars}
        # Also add underscore variables to test they're not substituted even if present
        variables.update(
            {"_private_var": "private", "__class__": "dangerous", "__dict__": "dangerous"}
        )

        # Valid variables should be substituted
        for var in valid_vars:
            template = f"{{{{ {var} }}}}"
            result = self.proxy._safe_template_substitute(template, variables)
            self.assertEqual(result, "value", f"Valid variable {var} should be substituted")

        # Invalid variables should be treated as having invalid syntax
        for var in invalid_vars:
            template = f"{{{{ {var} }}}}"
            with patch.object(self.proxy, 'log') as mock_log:
                result = self.proxy._safe_template_substitute(template, variables)
                self.assertIsNone(result, f"Invalid variable {var} should be rejected")
                mock_log.warning.assert_called_once()
                # Should warn about unsupported expressions since invalid var names don't match regex
                self.assertIn("Invalid template syntax", mock_log.warning.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
