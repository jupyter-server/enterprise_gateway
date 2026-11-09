# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for curl argument injection in the Conductor kernel launch path.

ConductorClusterProcessProxy splits the client-supplied KERNEL_CURL_SECURITY_OPT
value into individual curl arguments and splices them into the curl command
line.  No shell is involved, but an unvalidated value permits curl *argument*
injection (writing/reading files, loading a config, or a bare token curl treats
as an extra URL).  These tests assert the value is validated against a
fail-closed allowlist of curl SSL/TLS options.
"""

import unittest

from tornado import web

from enterprise_gateway.services.processproxies.conductor import (
    _CURL_SSL_VALUE_OPTS,
    validate_curl_security_opt,
)


class TestCurlSecurityOptValidation(unittest.TestCase):
    """Conductor: KERNEL_CURL_SECURITY_OPT must not permit curl argument injection."""

    def test_empty_value_yields_no_args(self):
        self.assertEqual(validate_curl_security_opt(""), [])

    def test_boolean_ssl_flag_allowed(self):
        self.assertEqual(validate_curl_security_opt("-k"), ["-k"])

    def test_value_ssl_flag_with_arg_allowed(self):
        self.assertEqual(
            validate_curl_security_opt("--cacert /etc/certs/ca.pem"),
            ["--cacert", "/etc/certs/ca.pem"],
        )

    def test_inline_equals_form_allowed(self):
        self.assertEqual(
            validate_curl_security_opt("--cacert=/etc/certs/ca.pem"),
            ["--cacert=/etc/certs/ca.pem"],
        )

    def test_multiple_ssl_options_allowed(self):
        raw = "--tlsv1.2 --cacert /etc/ca.pem --cert /etc/c.pem --key /etc/k.pem --insecure"
        self.assertEqual(validate_curl_security_opt(raw), raw.split())

    def test_output_flag_rejected(self):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("-o /home/jovyan/.bashrc")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_config_flag_rejected(self):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("-K /tmp/evil.conf")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_upload_file_flag_rejected(self):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("-T /etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_data_at_file_rejected(self):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("--data @/etc/passwd")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_bare_url_token_rejected(self):
        """A bare token would be interpreted by curl as an additional URL."""
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("http://attacker.example/exfil")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_bare_url_after_boolean_flag_rejected(self):
        """A boolean flag takes no arg, so a following bare token is a stray URL."""
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("-k http://attacker.example/exfil")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unknown_flag_rejected(self):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("--totally-made-up")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_inline_equals_disallowed_option_rejected(self):
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("--output=/tmp/x")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_dangling_value_option_rejected(self):
        """A trailing value-option would make curl consume the next fixed argument.

        The tokens are spliced in just before ``-b <cookie_jar>``, so a trailing
        ``--pass`` turns ``-b`` into the passphrase and the client-controlled
        cookie-jar path into an extra URL that receives the Authorization header.
        """
        with self.assertRaises(web.HTTPError) as ctx:
            validate_curl_security_opt("--pass")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_every_value_option_rejected_when_dangling(self):
        for opt in sorted(_CURL_SSL_VALUE_OPTS):
            with self.subTest(opt=opt):
                with self.assertRaises(web.HTTPError) as ctx:
                    validate_curl_security_opt(f"--tlsv1.2 {opt}")
                self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
