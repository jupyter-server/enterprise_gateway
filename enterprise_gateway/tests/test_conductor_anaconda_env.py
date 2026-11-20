# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Grammar validation for client-supplied KERNEL_ANACONDA_ENV (GHSA-99mg-9x9r-5fj4)."""

import pytest
from tornado import web

from enterprise_gateway.services.processproxies.conductor import (
    validate_conductor_anaconda_env,
)

# Values that must be rejected: the advisory PoC pipe payload, other shell
# metacharacters, whitespace word-splitting, path traversal, a leading dash, empty.
REJECTED = [
    "x|touch /tmp/pwned|y",
    "a;id",
    "a&&id",
    "a`id`",
    "a$(id)",
    "a b",
    "a\tb",
    "py39\n",
    "../../../../etc",
    "env/../../bin",
    "-env",
    "",
    "a\nb",
]

# Values that must be accepted: realistic conda environment names.
ACCEPTED = [
    "py39",
    "anaconda-2023.03",
    "my_env.1",
    "base",
    "_internal",
    "team-ds",
]


@pytest.mark.parametrize("anaconda_env", REJECTED)
def test_rejected(anaconda_env):
    with pytest.raises(web.HTTPError) as exc_info:
        validate_conductor_anaconda_env(anaconda_env)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("anaconda_env", ACCEPTED)
def test_accepted(anaconda_env):
    assert validate_conductor_anaconda_env(anaconda_env) is None


def test_rejection_does_not_echo_value():
    payload = "x|touch /tmp/pwned|y"
    with pytest.raises(web.HTTPError) as exc_info:
        validate_conductor_anaconda_env(payload)
    message = exc_info.value.log_message or ""
    assert payload not in message
    assert "touch" not in message
    assert "KERNEL_ANACONDA_ENV" in message


def test_length_cap():
    with pytest.raises(web.HTTPError) as exc_info:
        validate_conductor_anaconda_env("a" * 257)
    assert exc_info.value.status_code == 400
    assert validate_conductor_anaconda_env("a" * 256) is None
