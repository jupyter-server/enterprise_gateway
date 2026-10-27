# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for SSRF via KERNEL_CONDUCTOR_HA_ENDPOINTS (GHSA-f53v-m7jv-638m).

ConductorClusterProcessProxy fails over between Conductor (ascd) hosts when
the primary is unreachable.  The failover hosts come from the client-supplied
KERNEL_CONDUCTOR_HA_ENDPOINTS, and every request carries a JWT or EGO
PlatformToken in its Authorization header.  Clients must still be able to
choose their (team's) Conductor hosts, but only hosts inside the operator's
trust boundary may ever receive those credentials.
"""

import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from tornado import web

from enterprise_gateway.mixins import EnterpriseGatewayConfigMixin
from enterprise_gateway.services.processproxies import processproxy
from enterprise_gateway.services.processproxies.conductor import (
    ConductorClusterProcessProxy,
    _replace_url_host,
    validate_conductor_ha_endpoints,
)

PRIMARY = "ascd1.corp.example.com"
ASCD_ENDPOINT = f"https://{PRIMARY}:8643/platform/rest/conductor/v1"


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, []),
        ("", []),
        ("ascd2.corp.example.com", ["ascd2.corp.example.com"]),
        (
            "ascd2.corp.example.com,ascd3.corp.example.com",
            ["ascd2.corp.example.com", "ascd3.corp.example.com"],
        ),
        (
            " ASCD2.Corp.Example.COM , ascd3.corp.example.com ",
            ["ascd2.corp.example.com", "ascd3.corp.example.com"],
        ),
        ("ascd2.corp.example.com,,", ["ascd2.corp.example.com"]),
        ("ascd.team-a.corp.example.com", ["ascd.team-a.corp.example.com"]),
    ],
)
def test_hosts_in_endpoint_domain_are_accepted(value, expected):
    assert validate_conductor_ha_endpoints(value, PRIMARY) == expected


@pytest.mark.parametrize(
    "value",
    [
        "attacker.example.com",  # the advisory PoC
        "corp.example.com.attacker.net",  # allowed domain used as a prefix
        "evilcorp.example.com",  # suffix match must respect label boundaries
        "10.0.0.5",  # IP literals never match a DNS-domain boundary
        "ascd2",  # single-label name is outside the domain
    ],
)
def test_hosts_outside_endpoint_domain_are_rejected(value):
    with pytest.raises(web.HTTPError) as exc:
        validate_conductor_ha_endpoints(value, PRIMARY)
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "value",
    [
        # Each entry ends in ".corp.example.com", so only the bare-hostname rule
        # stops it.  Spliced into the request URL, the first four would send the
        # request to attacker.net.
        "attacker.net#.corp.example.com",
        "attacker.net/.corp.example.com",
        "attacker.net?.corp.example.com",
        "attacker.net:8443#.corp.example.com",
        "attacker.net\\.corp.example.com",
        "https://ascd2.corp.example.com",
        "ascd2 .corp.example.com",
        "-ascd2.corp.example.com",
        "ascd2..corp.example.com",
        "a" * 64 + ".corp.example.com",
    ],
)
def test_entries_that_are_not_bare_hostnames_are_rejected(value):
    with pytest.raises(web.HTTPError) as exc:
        validate_conductor_ha_endpoints(value, PRIMARY)
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "value",
    [
        "127.0.0.1",
        "169.254.169.254",  # cloud instance metadata
        "0.0.0.0",  # noqa: S104
        "0.1.2.3",
        "224.0.0.1",
        "255.255.255.255",
        "localhost",
        "ascd.localhost",
    ],
)
def test_internal_addresses_are_rejected_even_inside_the_boundary(value):
    allowed_hosts = ["0.0.0.0/0", "localhost"]
    with pytest.raises(web.HTTPError) as exc:
        validate_conductor_ha_endpoints(value, PRIMARY, allowed_hosts)
    assert exc.value.status_code == 400


def test_private_addresses_inside_the_boundary_are_accepted():
    """Enterprise Conductor hosts typically live on RFC 1918 networks."""
    assert validate_conductor_ha_endpoints("10.20.1.5", PRIMARY, ["0.0.0.0/0"]) == ["10.20.1.5"]


@pytest.mark.parametrize(
    "allowed_hosts",
    [
        ["team-a.example.org", "10.20.0.0/16"],
        "team-a.example.org,10.20.0.0/16",  # kernelspec proxy_config form
        [" .Team-A.example.org ", "10.20.0.0/16"],
        ["*.team-a.example.org", "10.20.0.0/16"],
    ],
)
@pytest.mark.parametrize(
    "value, accepted",
    [
        ("ascd.team-a.example.org", True),
        ("team-a.example.org", True),
        ("10.20.1.5", True),
        ("10.21.0.1", False),
        ("ascd.team-b.example.org", False),
        # A configured boundary replaces the endpoint-domain default.
        ("ascd2.corp.example.com", False),
    ],
)
def test_configured_boundary(allowed_hosts, value, accepted):
    if accepted:
        assert validate_conductor_ha_endpoints(value, PRIMARY, allowed_hosts) == [value]
    else:
        with pytest.raises(web.HTTPError) as exc:
            validate_conductor_ha_endpoints(value, PRIMARY, allowed_hosts)
        assert exc.value.status_code == 400


def test_blank_configured_entries_fall_back_to_endpoint_domain():
    """EG_CONDUCTOR_HA_ALLOWED_HOSTS unset parses to [""]; that is not a boundary."""
    assert validate_conductor_ha_endpoints("ascd2.corp.example.com", PRIMARY, [""]) == [
        "ascd2.corp.example.com"
    ]


def test_blank_configured_entry_does_not_match_every_host():
    with pytest.raises(web.HTTPError) as exc:
        validate_conductor_ha_endpoints("attacker.example.com", PRIMARY, ["", "team-a.example.org"])
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "primary_host, value",
    [
        ("10.0.0.1", "10.0.0.2"),  # IP-literal endpoint has no DNS domain
        ("ascd", "ascd2"),  # single-label endpoint has no DNS domain
        ("example.com", "attacker.com"),  # never derive a TLD-wide boundary
    ],
)
def test_no_derivable_boundary_rejects_entries(primary_host, value):
    with pytest.raises(web.HTTPError) as exc:
        validate_conductor_ha_endpoints(value, primary_host)
    assert exc.value.status_code == 400


def test_no_derivable_boundary_still_accepts_empty_value():
    assert validate_conductor_ha_endpoints("", "10.0.0.1") == []


def test_allowed_hosts_default_from_env(monkeypatch):
    monkeypatch.setenv("EG_CONDUCTOR_HA_ALLOWED_HOSTS", "team-a.example.org,10.20.0.0/16")
    config = EnterpriseGatewayConfigMixin()
    assert config.conductor_ha_allowed_hosts == ["team-a.example.org", "10.20.0.0/16"]


def _conductor_response(url: str) -> str:
    """Return a canned Conductor REST response for the JWT logon flow."""
    path = urlsplit(url).path
    if path.endswith("/auth/logon/jwt"):
        return '"platform-token"'
    if path.endswith("/auth/logon"):
        return '{"status": "ok"}'
    if "/anaconda/instances/" in path:
        return json.dumps({"parameters": {"deploy_home": {"value": "/opt/anaconda"}}})
    if path.endswith("/instances"):
        return json.dumps(
            [
                {
                    "sparkinstancegroup": {"sparkhomedir": "/opt/spark"},
                    "outputs": {
                        "batch_master_rest_urls": {"value": "spark://master:6066"},
                        "one_batch_master_web_submission_url": {"value": "https://master:8443"},
                    },
                }
            ]
        )
    msg = f"unexpected Conductor URL: {url}"
    raise AssertionError(msg)


class FakeCurl:
    """Stands in for ``subprocess.Popen`` running curl; records each invocation."""

    def __init__(self, unreachable=()):
        self.unreachable = set(unreachable)
        self.hosts = []
        self.cmds = []

    def __call__(self, cmd, **kwargs):
        self.cmds.append(list(cmd))
        url = cmd[-1]
        host = urlsplit(url).hostname
        self.hosts.append(host)
        proc = Mock()
        if host in self.unreachable:
            proc.communicate.return_value = (
                "",
                f"curl: (7) Failed connect to {host}:8643; Connection refused",
            )
        else:
            proc.communicate.return_value = (_conductor_response(url), "")
        return proc


def _make_proxy(proxy_config=None, allowed_hosts=None):
    """Build a ConductorClusterProcessProxy through its real __init__.

    Only the ResponseManager singleton is replaced, since it opens a listening
    socket that the test does not need.
    """
    kernel_manager = Mock()
    kernel_manager.kernel_id = "kernel-1"
    kernel_manager.port_range = "0..0"
    kernel_manager.unauthorized_users = set()
    kernel_manager.authorized_users = set()
    kernel_manager.conductor_endpoint = ASCD_ENDPOINT
    kernel_manager.conductor_ha_allowed_hosts = allowed_hosts if allowed_hosts is not None else []
    response_manager = Mock(response_address="127.0.0.1:8877", public_key="public-key")
    with patch.object(processproxy.ResponseManager, "instance", return_value=response_manager):
        return ConductorClusterProcessProxy(kernel_manager, proxy_config or {})


def _kernel_env(ha_endpoints=None):
    env = {
        "KERNEL_IG_UUID": "ig-uuid",
        "KERNEL_TOPOLOGY": "topology",
        "KERNEL_ANACONDA_INST_UUID": "anaconda-uuid",
        "KERNEL_ANACONDA_ENV": "py311",
        "KERNEL_NOTEBOOK_DATA_DIR": "/var/lib/notebook",
        "KERNEL_NOTEBOOK_COOKIE_JAR": "kernelcookie1",
        "KERNEL_CURL_SECURITY_OPT": "-k",
    }
    if ha_endpoints is not None:
        env["KERNEL_CONDUCTOR_HA_ENDPOINTS"] = ha_endpoints
    return env


def _jwt_logon(proxy, env, fake_curl):
    """Run the JWT logon flow (four authenticated REST calls) against fake curl."""
    proxy.env = env
    with patch("enterprise_gateway.services.processproxies.conductor.subprocess.Popen", fake_curl):
        proxy._performConductorJWTLogonAndRetrieval("user-jwt", env)


class TestConductorHAFailoverSink:
    """Authenticated Conductor calls only ever reach hosts inside the trust boundary."""

    def test_advisory_poc_host_is_rejected_before_any_request(self):
        """The advisory PoC: primary down, attacker host next in the HA list."""
        fake_curl = FakeCurl(unreachable={PRIMARY})
        with pytest.raises(web.HTTPError) as exc:
            _jwt_logon(_make_proxy(), _kernel_env("attacker.example.com"), fake_curl)
        assert exc.value.status_code == 400
        assert fake_curl.hosts == []

    def test_one_bad_entry_rejects_the_whole_list(self):
        fake_curl = FakeCurl(unreachable={PRIMARY})
        with pytest.raises(web.HTTPError) as exc:
            _jwt_logon(
                _make_proxy(),
                _kernel_env("ascd2.corp.example.com,attacker.example.com"),
                fake_curl,
            )
        assert exc.value.status_code == 400
        assert fake_curl.hosts == []

    def test_failover_host_in_endpoint_domain_is_used_when_primary_down(self):
        """With no operator config, hosts in the primary endpoint's domain are allowed."""
        fake_curl = FakeCurl(unreachable={PRIMARY})
        env = _kernel_env("ascd2.corp.example.com")
        _jwt_logon(_make_proxy(), env, fake_curl)
        assert fake_curl.hosts == [PRIMARY, "ascd2.corp.example.com"] * 4
        assert env["KERNEL_SPARK_HOME"] == "/opt/spark"

    def test_missing_ha_endpoints_uses_primary_only(self):
        fake_curl = FakeCurl()
        env = _kernel_env()
        _jwt_logon(_make_proxy(), env, fake_curl)
        assert fake_curl.hosts == [PRIMARY] * 4
        assert env["KERNEL_SPARK_HOME"] == "/opt/spark"

    @pytest.mark.parametrize(
        "ha_host, accepted",
        [
            ("ascd.team-a.example.org", True),
            # The operator boundary replaces the endpoint-domain default.
            ("ascd2.corp.example.com", False),
        ],
    )
    def test_gateway_allowed_hosts(self, ha_host, accepted):
        proxy = _make_proxy(allowed_hosts=["team-a.example.org"])
        self._assert_failover(proxy, ha_host, accepted)

    @pytest.mark.parametrize(
        "ha_host, accepted",
        [
            ("ascd.team-a.example.org", True),
            # The kernelspec value replaces the gateway-wide value.
            ("ascd.team-b.example.org", False),
        ],
    )
    def test_kernelspec_allowed_hosts_override_gateway(self, ha_host, accepted):
        proxy = _make_proxy(
            proxy_config={"conductor_ha_allowed_hosts": "team-a.example.org"},
            allowed_hosts=["team-b.example.org"],
        )
        self._assert_failover(proxy, ha_host, accepted)

    @staticmethod
    def _assert_failover(proxy, ha_host, accepted):
        fake_curl = FakeCurl(unreachable={PRIMARY})
        if accepted:
            _jwt_logon(proxy, _kernel_env(ha_host), fake_curl)
            assert fake_curl.hosts == [PRIMARY, ha_host] * 4
        else:
            with pytest.raises(web.HTTPError) as exc:
                _jwt_logon(proxy, _kernel_env(ha_host), fake_curl)
            assert exc.value.status_code == 400
            assert fake_curl.hosts == []


@pytest.mark.parametrize(
    "url, new_host, expected",
    [
        (
            "https://ascd1.corp.example.com:8643/auth/logon/jwt?topology=t",
            "ascd2.corp.example.com",
            "https://ascd2.corp.example.com:8643/auth/logon/jwt?topology=t",
        ),
        # The port of the endpoint is preserved; the host-only HA entry has none.
        (
            "https://ascd1.corp.example.com:8643/instances?id=1",
            "ascd2.corp.example.com",
            "https://ascd2.corp.example.com:8643/instances?id=1",
        ),
        # A ':' or '@' in the (client-controlled) query must stay in the query and
        # must not become part of the authority that curl connects to.
        (
            "https://ascd1.corp.example.com:8643/auth/logon/jwt?topology=t:1@evil.example",
            "ascd1.corp.example.com",
            "https://ascd1.corp.example.com:8643/auth/logon/jwt?topology=t:1@evil.example",
        ),
    ],
)
def test_replace_url_host_only_touches_authority(url, new_host, expected):
    result = _replace_url_host(url, new_host)
    assert result == expected
    assert urlsplit(result).hostname == new_host


class TestURLSpliceInjection:
    """Other KERNEL_* values interpolated into the URL cannot change the target host."""

    @pytest.mark.parametrize(
        "var",
        ["KERNEL_TOPOLOGY", "KERNEL_ANACONDA_INST_UUID", "KERNEL_IG_UUID"],
    )
    def test_colon_at_value_cannot_redirect_the_request(self, var):
        """A ':'/'@' bearing value would, with naive string surgery, move the host."""
        fake_curl = FakeCurl()  # primary reachable, no failover entries
        env = _kernel_env("")
        env[var] = "x:1@elsewhere.example.com/"
        _jwt_logon(_make_proxy(), env, fake_curl)
        assert set(fake_curl.hosts) == {PRIMARY}

    def test_ampersand_in_value_cannot_inject_query_parameters(self):
        """KERNEL_IG_UUID must be encoded so it cannot add/override query params."""
        fake_curl = FakeCurl()
        env = _kernel_env("")
        env["KERNEL_IG_UUID"] = "1&fields=secret"
        _jwt_logon(_make_proxy(), env, fake_curl)
        ig_call = next(c for c in fake_curl.cmds if "/instances?" in c[-1])
        query = parse_qs(urlsplit(ig_call[-1]).query)
        assert query["id"] == ["1&fields=secret"]
        assert query["fields"] == ["sparkinstancegroup,outputs"]


class TestCurlGlobbingAndTimeout:
    """curl must not expand URL globs, and must bound its connect time."""

    def test_all_curl_invocations_disable_globbing(self):
        fake_curl = FakeCurl()
        _jwt_logon(_make_proxy(), _kernel_env(""), fake_curl)
        assert fake_curl.cmds
        for cmd in fake_curl.cmds:
            assert "--globoff" in cmd or "-g" in cmd

    def test_all_curl_invocations_set_a_connect_timeout(self):
        fake_curl = FakeCurl()
        _jwt_logon(_make_proxy(), _kernel_env(""), fake_curl)
        for cmd in fake_curl.cmds:
            assert "--connect-timeout" in cmd


class TestHAListBounds:
    """The HA failover list is de-duplicated and capped."""

    def test_duplicate_entries_collapse(self):
        hosts = validate_conductor_ha_endpoints(
            "ascd2.corp.example.com,ascd2.corp.example.com,ascd3.corp.example.com",
            PRIMARY,
        )
        assert hosts == ["ascd2.corp.example.com", "ascd3.corp.example.com"]

    def test_entry_equal_to_primary_is_dropped(self):
        assert validate_conductor_ha_endpoints(f"{PRIMARY},ascd2.corp.example.com", PRIMARY) == [
            "ascd2.corp.example.com"
        ]

    def test_too_many_entries_rejected(self):
        many = ",".join(f"ascd{i}.corp.example.com" for i in range(64))
        with pytest.raises(web.HTTPError) as exc:
            validate_conductor_ha_endpoints(many, PRIMARY)
        assert exc.value.status_code == 400
