# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Authorization and grammar checks for client-supplied KERNEL_USERNAME (GHSA-vjjc-h367-2gx3)."""

import os
import unittest
from unittest.mock import Mock, patch

import pytest
from tornado import web

from enterprise_gateway.mixins import EnterpriseGatewayConfigMixin
from enterprise_gateway.services.processproxies.processproxy import (
    BaseProcessProxyABC,
    validate_kernel_username,
)

# Values that must be rejected: the denylist-bypass payload, its whitespace variants,
# argument-injection payloads, an option-flag lookalike, and shell metacharacters.
REJECTED_USERNAMES = [
    "root ",
    " root",
    "root\t",
    "root\troot",
    "nobody -u root",
    "alice --proxy-user root",
    "-u",
    "--proxy-user",
    "a b",
    "",
    "a$(id)",
    "a`id`",
    "a;id",
    "a|b",
    "a\nb",
]

# Values that must be accepted: ordinary accounts, email-style, dotted, digit/underscore starts.
ACCEPTED_USERNAMES = [
    "alice",
    "alice@example.com",
    "first.last",
    "user_1",
    "0day",
    "_svc",
    "a-b",
]


@pytest.mark.parametrize("kernel_username", REJECTED_USERNAMES)
def test_validate_kernel_username_rejects(kernel_username):
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_username(kernel_username)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("kernel_username", ACCEPTED_USERNAMES)
def test_validate_kernel_username_accepts(kernel_username):
    assert validate_kernel_username(kernel_username) is None


def test_validate_kernel_username_length_cap():
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_username("a" * 257)
    assert exc_info.value.status_code == 400
    assert validate_kernel_username("a" * 256) is None


def test_rejection_does_not_echo_username():
    secret = "root $(curl evil)"
    with pytest.raises(web.HTTPError) as exc_info:
        validate_kernel_username(secret)
    assert "curl evil" not in (exc_info.value.log_message or "")
    assert "KERNEL_USERNAME" in (exc_info.value.log_message or "")


class _StubProxy(BaseProcessProxyABC):
    """Concrete stand-in so the abstract base can be instantiated for authorization tests."""

    async def launch_process(self, kernel_cmd, **kwargs):
        return None

    def confirm_remote_startup(self):
        return None


def _make_authz_proxy(unauthorized=("root",), authorized=()):
    """Build a BaseProcessProxyABC subclass instance without its heavy __init__.

    _enforce_authorization only needs these attributes plus kwargs["env"].
    """
    proxy = _StubProxy.__new__(_StubProxy)
    proxy.log = Mock()
    proxy.unauthorized_users = set(unauthorized)
    proxy.authorized_users = set(authorized)
    proxy.kernel_manager = Mock()
    proxy.kernel_manager.impersonation_enabled = True
    proxy.kernel_manager.kernel_spec.display_name = "Spark Python (YARN Client)"
    return proxy


class TestEnforceAuthorizationUsername(unittest.TestCase):
    """_enforce_authorization validates KERNEL_USERNAME before the denylist check."""

    def test_trailing_space_root_is_rejected(self):
        proxy = _make_authz_proxy(unauthorized=("root",))
        with self.assertRaises(web.HTTPError) as ctx:
            proxy._enforce_authorization(env={"KERNEL_USERNAME": "root "})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_argument_injection_username_is_rejected(self):
        proxy = _make_authz_proxy(unauthorized=("root",))
        with self.assertRaises(web.HTTPError) as ctx:
            proxy._enforce_authorization(env={"KERNEL_USERNAME": "alice --proxy-user root"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_plain_root_still_denied_with_403(self):
        proxy = _make_authz_proxy(unauthorized=("root",))
        with self.assertRaises(web.HTTPError) as ctx:
            proxy._enforce_authorization(env={"KERNEL_USERNAME": "root"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_valid_user_is_allowed(self):
        proxy = _make_authz_proxy(unauthorized=("root",))
        # Returns None and does not raise.
        self.assertIsNone(proxy._enforce_authorization(env={"KERNEL_USERNAME": "alice"}))


class TestUserListTrimming(unittest.TestCase):
    """Operator lists are comma-separated with optional spaces; entries must be trimmed."""

    def test_unauthorized_users_entries_are_trimmed(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"EG_UNAUTHORIZED_USERS": "root, hdfs"}):
            config = EnterpriseGatewayConfigMixin()
            self.assertEqual(config.unauthorized_users, {"root", "hdfs"})

    def test_authorized_users_entries_are_trimmed(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"EG_AUTHORIZED_USERS": "alice, bob"}):
            config = EnterpriseGatewayConfigMixin()
            self.assertEqual(set(config.authorized_users), {"alice", "bob"})

    def test_unauthorized_users_empty_entries_are_dropped(self):
        with patch.dict(os.environ, {"EG_UNAUTHORIZED_USERS": "root,,hdfs ,"}):
            config = EnterpriseGatewayConfigMixin()
            self.assertEqual(config.unauthorized_users, {"root", "hdfs"})
