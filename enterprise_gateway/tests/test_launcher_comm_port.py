# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Regression tests shared by the Python and R communication port listeners."""

import importlib.util
import json
import socket
from pathlib import Path
from types import ModuleType

import pytest

LAUNCHERS = Path(__file__).parents[2] / "etc" / "kernel-launchers"
COPIES = {
    "python": LAUNCHERS / "python/scripts/launch_ipykernel.py",
    "r": LAUNCHERS / "R/scripts/server_listener.py",
}


@pytest.fixture(params=sorted(COPIES))
def launcher(request: pytest.FixtureRequest) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"launcher_{request.param}", COPIES[request.param]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _send(port: int, payload: bytes) -> None:
    with socket.create_connection(("127.0.0.1", port), timeout=2) as conn:
        conn.sendall(payload)


@pytest.mark.parametrize(
    "bad_payload", [b"", b"not json", b"\xff\xfe"], ids=["empty", "not-json", "bad-utf8"]
)
def test_bad_request_does_not_stop_listener(launcher: ModuleType, bad_payload: bytes) -> None:
    with launcher.prepare_comm_socket(0, 0) as sock:
        port = sock.getsockname()[1]

        _send(port, bad_payload)
        assert launcher.get_server_request(sock) is None

        _send(port, json.dumps({"signum": 2}).encode())
        assert launcher.get_server_request(sock) == {"signum": 2}


def test_listening_socket_errors_propagate(launcher: ModuleType) -> None:
    sock = launcher.prepare_comm_socket(0, 0)
    sock.close()
    with pytest.raises(OSError):
        launcher.get_server_request(sock)


def test_multibyte_request_across_receive_boundary(launcher: ModuleType) -> None:
    # The first byte of "é" lands at offset 1023, splitting it across 1024-byte reads.
    request = {"padding": "a" * 1010 + "é", "signum": 0}
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    assert payload[1023:1025] == "é".encode()
    with launcher.prepare_comm_socket(0, 0) as sock:
        _send(sock.getsockname()[1], payload)
        assert launcher.get_server_request(sock) == request
