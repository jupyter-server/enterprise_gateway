# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests that Conductor REST credentials are never written to the logs.

ConductorClusterProcessProxy logs the curl command it runs (at DEBUG, and at
WARNING on failures).  Those commands carry a JWT or EGO PlatformToken in an
``Authorization`` header, so the command must be redacted before it is logged.
"""

import logging

import pytest

from enterprise_gateway.services.processproxies.conductor import _redact_cmd
from enterprise_gateway.services.processproxies.processproxy import redaction_mask
from enterprise_gateway.tests.test_conductor_ssrf import (
    PRIMARY,
    FakeCurl,
    _jwt_logon,
    _kernel_env,
    _make_proxy,
)


class TestRedactCmd:
    """_redact_cmd masks Authorization header values and nothing else."""

    def test_bearer_token_is_masked(self):
        cmd = ["curl", "-H", "Authorization: Bearer super-secret-jwt", "https://ascd/x"]
        redacted = _redact_cmd(cmd)
        assert "super-secret-jwt" not in " ".join(redacted)
        assert redacted == ["curl", "-H", f"Authorization: {redaction_mask}", "https://ascd/x"]

    def test_platform_token_is_masked(self):
        cmd = ["curl", "-H", "Authorization: PlatformToken token=real-token", "https://ascd/x"]
        redacted = _redact_cmd(cmd)
        assert "real-token" not in " ".join(redacted)

    def test_header_name_match_is_case_insensitive(self):
        cmd = ["curl", "-H", "authorization: Bearer secret", "https://ascd/x"]
        assert f"authorization: {redaction_mask}" in _redact_cmd(cmd) or (
            f"Authorization: {redaction_mask}" in _redact_cmd(cmd)
        )
        assert "secret" not in " ".join(_redact_cmd(cmd))

    def test_multiple_authorization_headers_all_masked(self):
        cmd = [
            "curl",
            "-H",
            "Authorization: Bearer jwt-one",
            "-H",
            "Authorization: PlatformToken token=tok-two",
            "https://ascd/x",
        ]
        joined = " ".join(_redact_cmd(cmd))
        assert "jwt-one" not in joined
        assert "tok-two" not in joined

    def test_non_authorization_elements_are_preserved(self):
        cmd = [
            "curl",
            "--globoff",
            "-k",
            "-H",
            "Accept: application/json",
            "-H",
            "Authorization: Bearer secret",
            "https://ascd/instances?id=1",
        ]
        redacted = _redact_cmd(cmd)
        assert redacted[:6] == cmd[:6]  # everything up to the Authorization header is untouched
        assert redacted[-1] == "https://ascd/instances?id=1"

    def test_original_cmd_is_not_mutated(self):
        cmd = ["curl", "-H", "Authorization: Bearer secret", "https://ascd/x"]
        _redact_cmd(cmd)
        assert cmd[2] == "Authorization: Bearer secret"


class TestNoCredentialReachesTheLog:
    """End-to-end: running the JWT logon flow must not leak tokens to the log."""

    @pytest.fixture
    def captured(self, caplog):
        caplog.set_level(logging.DEBUG)
        return caplog

    def _run(self, fake_curl):
        proxy = _make_proxy()
        proxy.log = logging.getLogger("test.conductor.redaction")
        proxy.log.propagate = True
        _jwt_logon(proxy, _kernel_env(""), fake_curl)

    def test_tokens_absent_from_debug_logs_on_success(self, captured):
        # The JWT logon returns '"platform-token"', which becomes the PlatformToken
        # used on the following three calls; neither it nor the input JWT may appear.
        self._run(FakeCurl())
        assert "user-jwt" not in captured.text
        assert "platform-token" not in captured.text
        assert redaction_mask in captured.text

    def test_tokens_absent_from_warning_logs_on_failure(self, captured):
        # Primary unreachable -> HA exhausted -> the failing command is logged at WARNING.
        with pytest.raises(Exception):  # noqa: B017  (log_and_raise -> HTTPError/RuntimeError)
            self._run(FakeCurl(unreachable={PRIMARY}))
        assert "user-jwt" not in captured.text
