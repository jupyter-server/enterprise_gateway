# IBM Spectrum Conductor deployments

This information will be added shortly. The configuration is similar to that of [Hadoop YARN deployments](deploy-yarn-cluster.md) with the `ConductorClusterProcessProxy` used in place of `YARNClusterProcessProxy`.

The following sample kernel specifications are currently available on IBM Spectrum Conductor:

- spark_R_conductor_cluster
- spark_python_conductor_cluster
- spark_scala_conductor_cluster

## High-availability (HA) Conductor endpoints

When kernels authenticate to Conductor with a JWT (the `Jwt-Auth-User-Payload` kernel header), Enterprise Gateway
fails over to other Conductor (ascd) hosts if the configured `EG_CONDUCTOR_ENDPOINT` host is unreachable. The
failover hosts are supplied by the client in `KERNEL_CONDUCTOR_HA_ENDPOINTS`, a comma-separated list of hostnames,
so that each team or notebook server can target its own Conductor hosts. The scheme, port and path of
`EG_CONDUCTOR_ENDPOINT` are reused for every failover host.

Because these requests carry Conductor credentials, every entry is validated before any request is sent, and the
kernel start request fails with HTTP 400 if an entry:

- is not a bare hostname or IPv4 address (no scheme, port, path, query, fragment or user information),
- is an internal address (`localhost`, loopback, link-local such as `169.254.169.254`, multicast, reserved or
  unspecified), or
- is outside the trust boundary configured by the operator.

The trust boundary is configured with `--EnterpriseGatewayApp.conductor_ha_allowed_hosts` (or the
`EG_CONDUCTOR_HA_ALLOWED_HOSTS` environment variable), a list of DNS domains and IPv4 CIDRs. A domain matches the
domain itself and all of its subdomains; `corp.example.com`, `.corp.example.com` and `*.corp.example.com` are
equivalent. For example, to let teams use any Conductor host in their own subdomain or on the cluster network:

```bash
export EG_CONDUCTOR_HA_ALLOWED_HOSTS=team-a.example.com,team-b.example.com,10.20.0.0/16
```

When no trust boundary is configured, failover hosts must be in the DNS domain of the `EG_CONDUCTOR_ENDPOINT` host
(for `https://ascd1.corp.example.com:8643/...` that is `corp.example.com`). If that host is an IP address or has
fewer than three labels (e.g. `example.com`), there is no default domain and failover hosts are rejected until a
trust boundary is configured.

```{warning}
If the Conductor endpoint lives in a DNS namespace that other parties can register hosts in (for example a cloud
provider's load-balancer domain), the default boundary is too wide. Configure `EG_CONDUCTOR_HA_ALLOWED_HOSTS`
explicitly in that case.
```

The trust boundary can also be set per kernel specification with the `conductor_ha_allowed_hosts` entry of the
process-proxy `config` stanza, which replaces the gateway-wide value for that kernel:

```json
"metadata": {
  "process_proxy": {
    "class_name": "enterprise_gateway.services.processproxies.conductor.ConductorClusterProcessProxy",
    "config": {
      "conductor_ha_allowed_hosts": "team-a.example.com"
    }
  }
}
```

At most 16 distinct failover hosts may be supplied (duplicates and the primary host are ignored); a longer list is
rejected with HTTP 400. Each Conductor REST call is made with a bounded TCP connect time, configurable with the
`EG_CONDUCTOR_CONNECT_TIMEOUT` environment variable (seconds, default `10`), so that an unreachable failover host
cannot stall a kernel launch.
