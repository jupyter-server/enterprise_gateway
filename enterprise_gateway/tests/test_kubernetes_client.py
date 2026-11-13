# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for the kubernetes client behavior Enterprise Gateway depends on."""

from kubernetes import client
from kubernetes.config.incluster_config import InClusterConfigLoader

SERVICE_ACCOUNT_TOKEN = "fake-service-account-token"


def test_in_cluster_config_sends_service_account_token(tmp_path, monkeypatch):
    """In-cluster requests must carry the pod's service-account token.

    The gateway, its kernel launchers, and the kernel image puller all authenticate
    with ``config.load_incluster_config()``.  kubernetes 36.0.0 stored the token under
    an ``api_key`` entry that its own ``auth_settings()`` no longer read, so requests
    went out without an Authorization header, the API server treated them as
    ``system:anonymous``, and kernel launches failed with 403s.
    """
    token_file = tmp_path / "token"
    token_file.write_text(SERVICE_ACCOUNT_TOKEN)
    cert_file = tmp_path / "ca.crt"
    cert_file.write_text("not-a-real-ca")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "443")

    configuration = client.Configuration()
    InClusterConfigLoader(
        token_filename=str(token_file), cert_filename=str(cert_file)
    ).load_and_set(configuration)

    headers = {
        setting["key"].lower(): setting["value"]
        for setting in configuration.auth_settings().values()
        if setting["in"] == "header"
    }
    assert headers.get("authorization", "").lower() == f"bearer {SERVICE_ACCOUNT_TOKEN}"
